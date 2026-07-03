"""Crop-grain specialists for the offline extractor (E002: +pose, +emotion).

Canonical pose convention (the REGISTRY owns it — headpose-backend-decision):
degrees, 0 = camera-frontal; yaw signed (+ = subject's left turn as seen by
camera) so later view-binning (frontal/left/right) is derivable. MediaPipe
path: precise near-frontal; NO output on hard side faces → NaN, which is the
*correct* weak-prior signal. The angle math is the substrate's
``decompose_rotation_zyx`` (visualpath face-landmarks plugin) — one
convention, no per-backend drift.

Emotion: HSEmotion enet_b0_8 (onnx, ~/.hsemotion) — softmax probs mapped onto
the registry's em_* fields (legacy HSEmotion semantics, so the columns mean
what the field names say).
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

HSEMOTION_ONNX = Path.home() / ".hsemotion" / "enet_b0_8_best_vgaf.onnx"
LANDMARKER_TASK = Path.home() / ".cache" / "visualstack" / "mediapipe" / "face_landmarker.task"

# enet_b0_8 output order (HSEmotion 8-class, alphabetical) → registry field.
_HSE_ORDER = ("em_angry", "em_contempt", "em_disgust", "em_fear",
              "em_happy", "em_neutral", "em_sad", "em_surprise")

# MediaPipe face_landmarker blendshape order — captured from the model
# (2026-06, task bundle in ~/.cache/visualstack/mediapipe) and frozen as a
# CONTRACT; the extractor asserts the live model still agrees.
BLENDSHAPE_ORDER = (
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft",
    "browOuterUpRight", "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
    "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight",
    "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft",
    "mouthFrownRight", "mouthFunnel", "mouthLeft", "mouthLowerDownLeft",
    "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight", "mouthPucker",
    "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower",
    "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft",
    "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
    "noseSneerLeft", "noseSneerRight",
)


class PoseEstimator:
    """MediaPipe FaceLandmarker (IMAGE mode) on a padded face crop → degrees."""

    def __init__(self, task_path: Path = LANDMARKER_TASK) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(task_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            output_facial_transformation_matrixes=True,
            output_face_blendshapes=True,    # 52 universal expression coeffs
        ))
        self._bs_names: tuple[str, ...] | None = None   # captured on first hit

    @property
    def blendshape_names(self) -> tuple[str, ...] | None:
        return self._bs_names

    def close(self) -> None:
        """Release the mediapipe task graph explicitly — relying on __del__ at
        interpreter teardown raises a noisy (harmless) TypeError from mediapipe's
        dispatcher once its module globals are already torn down."""
        try:
            self._lm.close()
        except Exception:
            pass

    def __call__(self, crop_bgr: np.ndarray) -> dict | None:
        """→ {pose: (yaw,pitch,roll) deg, landmarks: (478,3) crop-normalized,
        transform: (4,4) canonical→camera} or None (side face → caller's NaN).

        Landmarks + matrix used to be discarded here; the appearance product
        reads geometry from their DISTRIBUTION (three-product-taxonomy), so
        the raw observation is now kept and stashed (landmarks.parquet) —
        canonicalization happens in the reading layer, like AU normalization.
        """
        from visualpath.plugins.face_landmarks.frontality import decompose_rotation_zyx

        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        res = self._lm.detect(img)
        if not res.facial_transformation_matrixes:
            return None                      # side face etc. → caller keeps NaN
        mat = np.asarray(res.facial_transformation_matrixes[0], dtype=np.float32)
        yaw, pitch, roll = decompose_rotation_zyx(mat)
        pts = np.array([[p.x, p.y, p.z] for p in res.face_landmarks[0]], dtype=np.float32)
        bs = res.face_blendshapes[0] if res.face_blendshapes else []
        if self._bs_names is None and bs:
            self._bs_names = tuple(c.category_name for c in bs)
        return {
            "pose": (math.degrees(yaw), math.degrees(pitch), math.degrees(roll)),
            "landmarks": pts,
            "transform": mat,
            "blendshapes": np.array([c.score for c in bs], dtype=np.float32),
        }


class EmotionEstimator:
    """HSEmotion enet_b0_8 onnx on a tight face crop → 8 probs (registry order)."""

    def __init__(self, onnx_path: Path = HSEMOTION_ONNX) -> None:
        import onnxruntime as ort

        self._sess = ort.InferenceSession(
            str(onnx_path), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self._input = self._sess.get_inputs()[0].name

    def __call__(self, crop_bgr: np.ndarray) -> dict[str, float] | None:
        if crop_bgr.shape[0] < 16 or crop_bgr.shape[1] < 16:
            return None
        x = cv2.cvtColor(cv2.resize(crop_bgr, (224, 224)), cv2.COLOR_BGR2RGB)
        x = (x.astype(np.float32) / 255.0 - np.array([0.485, 0.456, 0.406], dtype=np.float32)) \
            / np.array([0.229, 0.224, 0.225], dtype=np.float32)
        x = x.transpose(2, 0, 1)[None]
        logits = self._sess.run(None, {self._input: x})[0][0].astype(np.float64)
        p = np.exp(logits - logits.max())
        p /= p.sum()
        return dict(zip(_HSE_ORDER, p.tolist(), strict=True))


LIBREFACE_DIR = Path.home() / ".portrait981" / "models" / "libreface"

# LibreFace output order (DISFA) — matches registry AU_FIELDS order exactly.
_AU_ORDER = ("au1_inner_brow", "au2_outer_brow", "au4_brow_lowerer", "au5_upper_lid",
             "au6_cheek_raiser", "au9_nose_wrinkler", "au12_lip_corner", "au15_lip_depressor",
             "au17_chin_raiser", "au20_lip_stretcher", "au25_lips_part", "au26_jaw_drop")


class AUEstimator:
    """LibreFace two-stage onnx (E004): Encoder [1,3,224,224]→[1,512,1,1] →
    Intensity [1,512]→[1,12], DISFA 0–5 scale. Preprocess ported verbatim from
    legacy vpx face-au backend: RGB, resize 256 → center-crop 224, ImageNet norm.
    """

    def __init__(self, model_dir: Path = LIBREFACE_DIR) -> None:
        import onnxruntime as ort

        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._enc = ort.InferenceSession(str(model_dir / "LibreFace_AU_Encoder.onnx"), providers=prov)
        self._inten = ort.InferenceSession(str(model_dir / "LibreFace_AU_Intensity.onnx"), providers=prov)
        self._enc_in = self._enc.get_inputs()[0].name
        self._inten_in = self._inten.get_inputs()[0].name

    def __call__(self, crop_bgr: np.ndarray) -> dict[str, float] | None:
        if crop_bgr.shape[0] < 16 or crop_bgr.shape[1] < 16:
            return None
        rgb = cv2.cvtColor(cv2.resize(crop_bgr, (256, 256)), cv2.COLOR_BGR2RGB)
        x = rgb[16:240, 16:240].astype(np.float32) / 255.0
        x = (x - np.array([0.485, 0.456, 0.406], dtype=np.float32)) \
            / np.array([0.229, 0.224, 0.225], dtype=np.float32)
        x = x.transpose(2, 0, 1)[None]
        feat = self._enc.run(None, {self._enc_in: x})[0].reshape(1, 512)
        au = self._inten.run(None, {self._inten_in: feat})[0][0]
        au = np.clip(au, 0.0, 5.0)
        return dict(zip(_AU_ORDER, au.astype(float).tolist(), strict=True))
