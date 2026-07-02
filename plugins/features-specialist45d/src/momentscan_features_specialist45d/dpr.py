"""DPR (Deep Portrait Relighting, Zhou et al. ICCV'19) — SH lighting estimation.

Network + weights ported verbatim from legacy portrait981 face-lighting plugin
(dpr_v1.t7, 690K params); E009b gives the model its momentscan consumer
(portrait lighting quality — the face_light v0 pixel arithmetic's model-based
successor).

⚠️ SH coordinate convention (IMAGE frame, DPR's own):
  sh[0] = ambient
  sh[1] = Y (depth, into the image positive)
  sh[2] = Z (vertical, image-top positive)
  sh[3] = X (horizontal, image-right positive)
  sh[4:9] = 2nd order
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

DPR_T7 = Path.home() / ".portrait981" / "models" / "dpr" / "dpr_v1.t7"


def _build_net():
    import torch.nn as nn
    import torch.nn.functional as F

    def conv3x3(cin, cout):
        return nn.Conv2d(cin, cout, kernel_size=3, stride=1, padding=1, bias=False)

    class BasicBlock(nn.Module):
        def __init__(self, inplanes, outplanes, batchNorm_type=0):
            super().__init__()
            self.inplanes, self.outplanes = inplanes, outplanes
            self.conv1 = conv3x3(inplanes, outplanes)
            self.conv2 = conv3x3(outplanes, outplanes)
            norm = nn.BatchNorm2d if batchNorm_type == 0 else nn.InstanceNorm2d
            self.bn1, self.bn2 = norm(outplanes), norm(outplanes)
            self.shortcuts = nn.Conv2d(inplanes, outplanes, kernel_size=1, stride=1, bias=False)

        def forward(self, x):
            out = F.relu(self.bn1(self.conv1(x)))
            out = self.bn2(self.conv2(out))
            out = out + (self.shortcuts(x) if self.inplanes != self.outplanes else x)
            return F.relu(out)

    class HourglassBlock(nn.Module):
        def __init__(self, inplane, mid_plane, middleNet):
            super().__init__()
            self.upper = BasicBlock(inplane, inplane, batchNorm_type=1)
            self.downSample = nn.MaxPool2d(kernel_size=2, stride=2)
            self.upSample = nn.Upsample(scale_factor=2, mode="nearest")
            self.low1 = BasicBlock(inplane, mid_plane)
            self.middle = middleNet
            self.low2 = BasicBlock(mid_plane, inplane, batchNorm_type=1)

        def forward(self, x, light, count, skip_count):
            out_upper = self.upper(x)
            out_lower = self.low1(self.downSample(x))
            out_lower, out_middle = self.middle(out_lower, light, count + 1, skip_count)
            out_lower = self.upSample(self.low2(out_lower))
            return (out_lower + out_upper if count >= skip_count else out_lower), out_middle

    class LightingNet(nn.Module):
        def __init__(self, ncInput, ncOutput, ncMiddle):
            super().__init__()
            self.ncInput = ncInput
            self.predict_FC1 = nn.Conv2d(ncInput, ncMiddle, kernel_size=1, stride=1, bias=False)
            self.predict_relu1 = nn.PReLU()
            self.predict_FC2 = nn.Conv2d(ncMiddle, ncOutput, kernel_size=1, stride=1, bias=False)
            self.post_FC1 = nn.Conv2d(ncOutput, ncMiddle, kernel_size=1, stride=1, bias=False)
            self.post_relu1 = nn.PReLU()
            self.post_FC2 = nn.Conv2d(ncMiddle, ncInput, kernel_size=1, stride=1, bias=False)
            self.post_relu2 = nn.ReLU()

        def forward(self, innerFeat, target_light, count, skip_count):
            x = innerFeat[:, : self.ncInput, :, :]
            _, _, row, col = x.shape
            light = self.predict_FC2(self.predict_relu1(self.predict_FC1(
                x.mean(dim=(2, 3), keepdim=True))))
            upFeat = self.post_relu2(self.post_FC2(self.post_relu1(self.post_FC1(target_light))))
            innerFeat[:, : self.ncInput, :, :] = upFeat.repeat((1, 1, row, col))
            return innerFeat, light

    class HourglassNet(nn.Module):
        def __init__(self, baseFilter=16):
            super().__init__()
            self.ncLight, self.ncPre = 27, baseFilter
            ncHG3, ncHG2, ncHG1 = baseFilter, 2 * baseFilter, 4 * baseFilter
            ncHG0 = 8 * baseFilter + self.ncLight
            self.pre_conv = nn.Conv2d(1, self.ncPre, kernel_size=5, stride=1, padding=2)
            self.pre_bn = nn.BatchNorm2d(self.ncPre)
            self.light = LightingNet(self.ncLight, 9, 128)   # gray model: 9 SH out
            self.HG0 = HourglassBlock(ncHG1, ncHG0, self.light)
            self.HG1 = HourglassBlock(ncHG2, ncHG1, self.HG0)
            self.HG2 = HourglassBlock(ncHG3, ncHG2, self.HG1)
            self.HG3 = HourglassBlock(self.ncPre, ncHG3, self.HG2)
            self.conv_1 = nn.Conv2d(self.ncPre, self.ncPre, kernel_size=3, stride=1, padding=1)
            self.bn_1 = nn.BatchNorm2d(self.ncPre)
            self.conv_2 = nn.Conv2d(self.ncPre, self.ncPre, kernel_size=1, stride=1)
            self.bn_2 = nn.BatchNorm2d(self.ncPre)
            self.conv_3 = nn.Conv2d(self.ncPre, self.ncPre, kernel_size=1, stride=1)
            self.bn_3 = nn.BatchNorm2d(self.ncPre)
            self.output = nn.Conv2d(self.ncPre, 1, kernel_size=1, stride=1)

        def forward(self, x, target_light, skip_count):
            feat = F.relu(self.pre_bn(self.pre_conv(x)))
            _, out_light = self.HG3(feat, target_light, 0, skip_count)
            return None, out_light   # relighting head unused — SH only

    return HourglassNet()


class LightingEstimator:
    """DPR SH on a padded face crop → (9,) float64, DPR image-frame convention."""

    def __init__(self, model_path: Path = DPR_T7) -> None:
        import torch

        self._torch = torch
        net = _build_net()
        net.load_state_dict(torch.load(str(model_path), map_location="cpu", weights_only=True))
        net.eval()
        self._dev = "cuda" if torch.cuda.is_available() else "cpu"
        self._net = net.to(self._dev)
        self._zero_sh = torch.zeros(1, 9, 1, 1, device=self._dev)

    def __call__(self, crop_bgr: np.ndarray) -> np.ndarray | None:
        if crop_bgr.shape[0] < 16 or crop_bgr.shape[1] < 16:
            return None
        # DPR input: L of Lab, 512×512 (legacy-faithful: plain resize)
        lab = cv2.cvtColor(cv2.resize(crop_bgr, (512, 512)), cv2.COLOR_BGR2LAB)
        x = self._torch.from_numpy(lab[:, :, 0].astype(np.float32) / 255.0)[None, None]
        with self._torch.no_grad():
            _, sh = self._net(x.to(self._dev), self._zero_sh, 0)
        return sh.squeeze().cpu().numpy().astype(np.float64)
