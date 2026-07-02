# Handoff ← visualstack: depth plugin + viz primitives (resolved)

**Status:** ✅ visualstack 쪽 작업 완료 (2026-06-08). momentscan은 새 결로
import해서 쓰기만 하면 됨.

원래 핸드오프는 portrait981의 두 자리를 그대로 visualstack에 이식하려 했지만,
visualstack 일관성 검토 후 **결을 재해석**해서 풀었음. 아래는 *결과로 합의된*
인터페이스와 위치.

---

## ① Depth — `visualpath-plugin-depth`

portrait981 `apps/momentscan/src/momentscan/app/depth.py`의 도메인-무관 2개 메서드를
**standalone class**로 옮겼음. bus Module이 아니라, sampled frame에 직접 호출하는
estimator.

**왜 plugin Module이 아닌가:** depth-anything-v2-small 추론 ≈ 수백 ms/장. per-frame
plugin으로 만들면 30 fps × 1 분 = 1800 추론 → 비현실. clip당 sampled frame 몇 개에만
돌리는 게 본질이라, plugin *distribution* 컨벤션만 따르고 bus integration은 도입하지
않음. plugin/distribution 위치인 이유는 torch + transformers 의존성을 다른 plugin과
분리 distribute할 수 있게 하기 위함 (현재는 단일 venv에서도 공존).

### Import 계약

```python
from visualpath.plugins.depth import DepthEstimator
from visualbus import BBox

est = DepthEstimator()                              # lazy-init on first call
# 또는: DepthEstimator(model_id="depth-anything/Depth-Anything-V2-Base-hf", device="cuda")

depth_map = est.estimate_depth(image_bgr)
# (H, W) float32, 높을수록 카메라에 가까움 (Depth-Anything 컨벤션).
# 모델 unavailable이면 None.

closer = est.compare_region_depth(
    image_bgr,
    BBox(x1=100, y1=50, x2=300, y2=400),            # BBox 또는 (x1,y1,x2,y2) tuple
    BBox(x1=400, y1=50, x2=600, y2=400),
)
# "a" / "b" / None
```

### portrait981 → visualstack 매핑

| portrait981 | visualstack | 변경 |
|---|---|---|
| `DepthSeatAssigner` class | `DepthEstimator` | 도메인 어휘 "seat" 제거 |
| `compare_face_depth(img, bbox_a, bbox_b)` | `compare_region_depth(img, bbox_a, bbox_b)` | "face" → "region" |
| bbox: normalized xywh `(x,y,w,h) ∈ [0,1]` | **absolute pixel xyxy** (`BBox` or tuple) | visualbus `Detection.bbox`와 일관 |
| 모델 id 메서드 안에 박힘 | `__init__(model_id=...)` 인자 | default 동일, override 가능 |
| `device` 자동 (cuda if available) | `__init__(device=None)` | None = 자동, "cuda"/"cpu" 명시 가능 |
| `assign_driver(...)` | (포팅 X) | momentscan 도메인 — 자체 구현 |
| `_find_bbox(...)` | (포팅 X) | momentscan 도메인 |

### momentscan 쪽 작업

- `tubelets.py`(혹은 step0b)에서 `from visualpath.plugins.depth import DepthEstimator`
- 2-person sampled frame을 골라 `compare_region_depth(img, bbox_a, bbox_b)` 호출
- voting / `rider_role="main"` / seat 어휘는 momentscan 코드에. visualstack은
  *어느 박스가 더 가까운지*만 알려주고 의미부여는 호출자 몫.
- bbox는 visualbus `Detection.bbox` (absolute xyxy)를 그대로 전달.
  portrait981 시절의 normalized xywh 변환 불필요.

---

## ② Viz — vpx-viz 이동 폐기, visualbus 결로 통합

**원안 (vpx-viz를 `visualpath.viz`로 이동)은 진행하지 않음.** visualbus가 이미
*push pattern*의 overlay 시스템을 갖고 있고, vpx-viz의 *pull pattern*
(`module.annotate(obs) → marks`)을 들이면 visualstack 내부에 평행한 두 render 결이
공존하게 됨. visualstack 일관성을 위해 vpx-viz는 옮기지 않고, momentscan이 필요한
기능은 **visualbus 결로** 노출함.

### momentscan이 쓸 surface

```python
from visualbus import (
    apply_hint,             # frame BGR ndarray에 RenderHint 한 개 그리기 (in-place)
    DrawBBox, DrawKeypoint, DrawText, DrawMask,    # hint dataclasses
    VideoFileSink,          # bus 구독자: frame/* + render_hint__* → annotated mp4
    WindowRenderAction,     # 같은 기능의 live cv2.imshow 버전
)
```

### 두 가지 사용 패턴

**(A) bus 위에서 publish-driven 렌더링** — 가장 visualstack-native:

```python
from visualbus import VisualBus, FileSource, VideoFileSink

with VisualBus() as bus:
    sink = VideoFileSink("trace.mp4", fps=30.0)
    sink.attach(bus)                                # frame/* + signal/render_hint__* 구독
    # depth dense map 같은 거 alpha blend 하고 싶으면:
    # sink.attach(bus, dense_topics=["signal/depth__monocular"])

    pipeline.attach_to(bus)                         # 플러그인들이 render_hint publish
    bus.attach_source(FileSource("clip.mp4"), name="job")
    bus.run_until_done()
    sink.close()
```

**(B) bus 밖에서 직접 그리기** — stashed tubelet → mp4 같은 *offline 합성*:

```python
import cv2
from visualbus import DrawBBox, DrawText, apply_hint, BBox

writer = cv2.VideoWriter("trace.mp4", cv2.VideoWriter_fourcc(*"mp4v"),
                         fps, (w, h))
for frame_id, img, marks in frames_with_marks():
    for mark in marks:
        # marks는 momentscan이 정의한 자료구조. DrawBBox/DrawText로 변환:
        hint = DrawBBox(frame_id=frame_id, bbox=mark.bbox, color=(0,255,0),
                        thickness=2, label=mark.label)
        apply_hint(img, hint)
    writer.write(img)
writer.release()
```

→ stashed tubelet → trace.mp4 같이 *bus를 쓰지 않는* 자리는 (B) 결로. helper로
들고 다닐 만큼 반복되면 momentscan-side utility로 추출.

### Hint 타입 매핑 (vpx-viz → visualbus)

| vpx-viz `Mark` (portrait981) | visualbus `RenderHint` | 비고 |
|---|---|---|
| `BBoxMark(x,y,w,h, label, color)` (normalized xywh) | `DrawBBox(frame_id, bbox: BBox, label, color, thickness)` | bbox는 absolute xyxy |
| `LabelMark(text, x, y)` | `DrawText(frame_id, text, x, y, color, font_scale, thickness)` | absolute px |
| `KeypointsMark(points, connections)` | `DrawKeypoint(frame_id, keypoints: KeypointSet, color, radius, draw_connections)` | `KeypointSet`에 connections 들어있음 |
| `BarMark(x,y,w, value)` (progress bar) | (없음) | 두 번째 reuse 생기면 추가 |
| `AxisMark(cx,cy, yaw,pitch,roll)` (3D pose axes) | (없음 — head-pose plugin이 cv2로 직접 그림) | 필요 시 추가 |

`BarMark` / `AxisMark`는 momentscan이 실제로 필요한 시점에 visualbus에 hint 추가
PR. 지금 만들지 않음 (premature).

### `FrameDisplay` / `VideoSaver` (vpx-viz)는?

- `FrameDisplay` ≈ visualbus `WindowRenderAction` — 후자가 더 풍부. 새로 안 만듦.
- `VideoSaver` ≈ visualbus `VideoFileSink` — 위에서 신규 추가됨. 기능 동등 + bus
  결로 통합.

### Observation 모델 (`obs.source`, `obs.signals`)은?

vpx-viz의 `TextOverlay` / `MarkOverlay`는 portrait981 `Observation` 객체에 묶여
있었음. visualstack에는 그 모델이 없음 — bus에서는 토픽별 payload가 결. momentscan이
HUD에 "source / signals" 표시가 필요하면, 직접 `DrawText` hint를 publish하거나
HUD overlay 객체 (`render(img)` 메서드) 만들어 `VideoFileSink(hud_overlays=[...])`로
주입. visualstack 안에 일반화된 Observation 자료형은 도입하지 않음.

---

## 변경된 파일 (visualstack)

```
visualstack/
├── pyproject.toml                        # workspace source: visualpath-plugin-depth 추가
├── plugins/depth/                        # NEW distribution
│   ├── pyproject.toml                    # torch + transformers + pillow
│   └── src/visualpath/plugins/depth/
│       ├── __init__.py                   # exports DepthEstimator
│       └── estimator.py                  # standalone class, lazy-init
└── visualbus/src/visualbus/
    ├── __init__.py                       # re-export VideoFileSink
    └── overlay/
        ├── __init__.py                   # re-export VideoFileSink
        └── video_file.py                 # NEW — WindowRenderAction의 mp4 변종
```

검증:
- `from visualpath.plugins.depth import DepthEstimator` import 성공
- 실제 추론: 2154×1436 BGR → (1436, 2154) float32 depth map, GPU cuda 로딩 ✓
- `compare_region_depth(img, BBox, BBox)` / `(img, tuple, tuple)` 모두 동작
- `VideoFileSink` 3-frame 합성 → readable mp4 ✓ (`n_written == 3`, `cv2.VideoCapture` readback == 3)

---

## 폐기된 결정

이전 핸드오프 doc의 다음 항목은 *진행하지 않음*:
- `visualstack/visualpath/viz/` workspace member 생성
- `vpx-viz` (`vpx.viz.*` 5개 public API) 그대로 이동
- portrait981 `Observation` 모델 의존
- normalized xywh bbox API

대체된 결은 위에 명시.
