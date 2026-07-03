# momentscan 좌표계 규약 — 서술 스펙

> 형식은 `visualstack/docs/coordinate-conventions.md`를 미러링(2026-07-02, appearance-engine
> 조사에서 이식). **코드 상수의 단일 진실은 각 홈**(아래 표) — 이 문서는 홈들에 흩어진
> 규약을 한 장에 고정하고, 정합 관계를 **측정 근거와 함께** 서술한다. 요약표는
> [`ARCHITECTURE.md`](../ARCHITECTURE.md) 좌표계 지도.

## 1. 공간 정의

| 공간 | 정의 | 코드 홈 |
|---|---|---|
| 이미지/픽셀 | origin TL · +X right · **+Y down** · BGR(cv2) · bbox=xyxy 절대픽셀 | `subjects/crops.py`(portrait_box) · `media.py` |
| 크롭 트랙 | portrait_box(4:5, face=FACEH) → 고정 캔버스 레터박스(무왜곡) · crop-frame i↔원본 frame_idx = manifest | `subjects/crops.py` |
| MP 오일러 | `pose.euler_from_transform(M)`의 출력이 **정의 그 자체** (deg, 0=frontal) | `domains/pose.py` |
| 랜드마크 정준 프레임 | origin=centroid · axis_flip **(1,−1,−1)** (π about x: image y-down/z-in → camera y-up/z-out, det=+1 가드) · scale=rms 무차원 · basis 478/468 | `domains/geometry.py` CANONICAL_FRAME |
| ARKit blendshape | 52축 활성도(무차원, 좌표 아님) · 인덱스 계약=`signals.BS_*` · 생성 리그와 공유(render-query) | `domains/signals.py` |

## 2. 오일러 규약

- **정의적 홈 = `pose.euler_from_transform`**: MP facial-transformation matrix → (yaw, pitch, roll) deg.
  분해식: yaw=atan2(−R20, √(R00²+R10²)) · pitch=atan2(R21, R22) · roll=atan2(R10, R00).
- 의미 축이름의 소유 = registry:POSE_FIELDS (재정의 금지, CANONICAL_FRAME도 참조만).
- **⚠ 사람-의미 부호표(+yaw=어느 쪽?)는 아직 미고정** — visualstack canonical은
  (+yaw=viewer right, +pitch=up, +roll=viewer CW)를 선언하고 MP raw는 거기서 pitch·roll이
  뒤집힌 관계지만, momentscan 데이터의 시각 검증(아래 §4 invariant)으로 고정하기 전까지
  단정하지 않는다. 코드가 소비하는 것은 관계(정합)와 |·| 콘뿐이라 현재 무해.

## 3. 백엔드 → momentscan 규약 투영표

| 백엔드 | raw 좌표계 | 투영(어댑터) | 근거(측정) |
|---|---|---|---|
| MediaPipe transform | 정의 그 자체 | 항등 | — |
| 6DRepNet (300W-LP) | MP 오일러의 **3축 전미러** | **(−yaw, −pitch, −roll)** @`extraction/headpose.py` | MP-커버 프레임 축별 부호-corr: raw −0.97/−0.695/−0.629 → flip 후 +0.85/+0.57/+0.68, 부호 6/6클립 일관, median offset ≤1° (2026-07-02, n=6558/9클립) |
| (교차확인) visualstack | canonical에 MP=(y,−p,−r)·6D=(−y,p,r) 투영 | → 두 raw의 상호관계 = 3축 전미러 | 독립 유도가 측정과 일치 |

**규칙**: 새 포즈/기하 백엔드 추가 시 어댑터에서 투영 + **측정 검증 필수**
(커버 교집합 프레임에서 축별 부호-corr; "yaw만 맞추고 통과"가 2026-07-02까지의 잠복 지뢰 —
융합 스트림 `pit_f/rol_f`가 프레임 소스별 좌표 혼합, abs() 소비자뿐이라 무사했음).

## 4. 검증 invariant (좌표 버그의 동결 지점)

| invariant | 지킴이 |
|---|---|
| CANONICAL_FRAME.axis_flip은 proper rotation (det=+1) — reflection이면 PC1↔yaw 상관 붕괴(−0.996→+0.09 실측 교훈) | `geometry.py` import-시 assert |
| 백엔드 정합: MP-커버 프레임에서 6D와 축별 corr 전부 양수 | 어댑터 변경 시 측정 (§3 방법) |
| blendshape 인덱스: BS_BLINK=(9,10)·BS_SMILE=(42,43)·BS_JAW=25 | `signals.py` 상수 |
| 크롭↔원본 프레임 정렬: manifest frames가 유일 매핑 · fps 일치 필수 | `crops.py` manifest |
| (미고정) 사람-의미 부호: "명백히 아래를 보는 프레임"의 pitch 부호를 시각 검증으로 고정 | TODO — pitch 활용(클립-상대 가드) 착수 시 |

## 5. 변경 절차

좌표/규약 변경 = ①이 문서와 코드 홈 동시 갱신 ②§3 측정 재실행 ③영향 artifact 재생성
(headpose.parquet·gate_trace) ④게이트 결정 델타 확인(abs 콘은 부호 불변이어야)
⑤replay-check. — 2026-07-02 6D 3축 정렬이 이 절차의 전례(결정 델타 0/13 subjects).
