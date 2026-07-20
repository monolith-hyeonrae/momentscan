"""Cat G 축 정책·캘리 상수 — recipe 스테이지가 face_axes 값에 입히는 도메인 정책.

출처: appearance-engine `output/registry.json`(88축 레지스트리) + `build_axes_
registry.py:45-65 _CALIBRATED_G_RANGES` 흡수 (2026-07-20, absorption-plan §1 A3).

**비밀 2종 분리 (change-forecast ③)**: 이 모듈은 *정책*만 소유한다 — 축 ID·한글
라벨·타입·시간척도·설명(도메인 정책 비밀)과 캘리 range(캘리-코퍼스 비밀). 랜드마크
산식(측정 기판 비밀)은 여기 없다 — 그 절반은 `perception/readings/face_axes.py`.

**왜 preset/ 이 아니라 여기(products/ 파이썬 상수)인가** (A3): 캘리 range 는 시설/
기구 축이 아니라 캘리-코퍼스 축이다(preset 의 장비-색 제외 리스트와 반대 성질).
또 파이썬 상수라 값 수정 → import 클로저가 recipe 를 자동 stale 시킨다 — json 이면
freshness._external_deps 수동 등재를 빠뜨리는 test_3 무증상 실명 경로가 열린다.

**왜 88축 전부가 아니라 G 메타 + 미충전 ID 인가**: recipe 는 오늘 Cat G(37축)만
채우고 나머지(C/H/A/S/W)는 unfilled 로 ID만 정직 보고한다. 그 카테고리들의 한글
라벨은 momentscan 내 소비자(채우는 스테이지)가 아직 없다 — 소비자보다 먼저 짓지
않는다(change-forecast ②). 채우는 날 그 메타를 여기 승격한다.
"""

from __future__ import annotations

from momentscan.perception.readings.face_axes import AXIS_NAMES

# registry.json 스냅샷 버전 — recipe.registry_version 으로 방출(정책 출처 도장).
REGISTRY_VERSION = "appearance-engine-v0.1.0+calib.race981-20260720"  # L-B 판정: race981 캘리 전환

G_CATEGORY_NAME = "Face Geometry"

# 캘리 range [p5, p95] — appearance-engine sample_1(17 인물, L/R 랜드마크 풀링)에서
# 관측된 백분위. blame = calibrated:sample_1[p5,p95]. G37(범주형)·미채움 축엔 range
# 없음(None). 재캘리(원장 ①)는 momentscan 코퍼스 기준 새 도구 소관 — 그때 이 한
# 상수만 교체하면 recipe 가 자동 stale 재계산된다.
_CALIBRATED_G_RANGES: dict[str, tuple[float, float]] = {
    "G01": (0.763, 0.897),
    "G02": (0.74, 0.829),
    "G03": (99.273, 128.528),
    "G04": (0.72, 0.789),
    "G05": (0.26, 0.307),
    "G06": (0.164, 0.209),
    "G07": (0.164, 0.209),
    "G08": (0.121, 0.367),
    "G09": (0.121, 0.367),
    "G10": (0.121, 0.367),
    "G11": (0.121, 0.367),
    "G12": (0.412, 0.499),
    "G13": (-1.165, 8.652),
    "G14": (-1.165, 8.652),
    "G15": (0.254, 0.304),
    "G16": (0.2, 0.239),
    "G17": (0.172, 0.197),
    "G18": (124.702, 157.606),
    "G19": (0.027, 0.049),
    "G20": (0.038, 0.072),
    "G21": (0.324, 0.455),
    "G22": (-17.955, 53.107),
    "G23": (0.077, 0.113),
    "G24": (0.828, 0.935),
    "G25": (0.336, 0.971),
    "G26": (0.987, 1.54),
    "G27": (0.987, 1.54),
    "G28": (0.301, 0.473),
    "G29": (0.301, 0.473),
    "G30": (0.179, 0.289),
    "G31": (0.179, 0.289),
    "G32": (-4.976, 6.095),
    "G33": (-4.976, 6.095),
    "G34": (0.038, 0.072),
    "G35": (0.166, 0.209),
    "G36": (0.227, 0.301),
}

# 재캘리 range [p5, p95] — momentscan race981 코퍼스 기준(원장 ①, 캘리 양안).
# blame = calibrated:race981-corpus[p5,p95]. **방법**: output/l2 15 클립의 main-rider
# recipe.json 에서 categories["Face Geometry"][aid]["value"] 수집 → 구 테이블과 동일한
# L/R 풀링 그룹({G06,G07}·{G08~G11}·{G13,G14}·{G26,G27}·{G28,G29}·{G30,G31}·{G32,G33})
# 으로 풀링 → numpy percentile(linear) → round(…, 3). n = 15 (풀링 그룹 30~60). 정면-전용
# neutral 기하 위에서 측정(원장 ⑧ 반영). 산출일 2026-07-20. 추출 스크립트는 일회성이라
# 커밋하지 않음(방법은 이 주석이 정본).
#
# ⚠ n=15 → p5/p95 는 사실상 near-extremes(15점 선형보간) — A/B 판정용 시작점이지 확정
# 분포가 아니다. **계통 오프셋**(구=지인 17명 단일-이미지 posed / 신=비디오 집계 정면
# neutral): mouth_corner(G22) 구 p95 53° → 신 26°(posed 미소 편향 제거), brow_slope
# (G32/G33) mid +2.3°, brow_thickness(G28/G29) mid −0.09(구 p5 아래로 포화하던 값이
# 창 안으로), lip(G19/G20) 상향, face_symmetry(G25) 0.34–0.97 → 0.90–0.99(정면-전용의
# 높은 대칭). 4키 가장자리 포화(Brow_Thickness≈0·Mouth_Size≈0.9·Mouse_Corner 하향·
# Brow_Slant 상향)의 해소는 --ab calib 몽타주·포화 수치표(track/lk-calib 보고)로 실증.
_CALIBRATED_G_RANGES_RACE981: dict[str, tuple[float, float]] = {
    "G01": (0.837, 0.995),
    "G02": (0.8, 0.854),
    "G03": (113.628, 124.38),
    "G04": (0.744, 0.799),
    "G05": (0.246, 0.28),
    "G06": (0.167, 0.21),
    "G07": (0.167, 0.21),
    "G08": (0.291, 0.395),
    "G09": (0.291, 0.395),
    "G10": (0.291, 0.395),
    "G11": (0.291, 0.395),
    "G12": (0.438, 0.481),
    "G13": (2.619, 8.513),
    "G14": (2.619, 8.513),
    "G15": (0.255, 0.3),
    "G16": (0.195, 0.219),
    "G17": (0.17, 0.196),
    "G18": (149.844, 165.329),
    "G19": (0.039, 0.052),
    "G20": (0.055, 0.071),
    "G21": (0.353, 0.408),
    "G22": (-22.134, 25.666),
    "G23": (0.081, 0.118),
    "G24": (0.847, 0.918),
    "G25": (0.898, 0.988),
    "G26": (1.046, 1.26),
    "G27": (1.046, 1.26),
    "G28": (0.252, 0.334),
    "G29": (0.252, 0.334),
    "G30": (0.183, 0.238),
    "G31": (0.183, 0.238),
    "G32": (0.863, 4.926),
    "G33": (0.863, 4.926),
    "G34": (0.032, 0.043),
    "G35": (0.175, 0.202),
    "G36": (0.22, 0.281),
}

# 캘리 테이블 레지스트리 — 이름이 출처를 읽게 한다. --ab calib(원장 ①) 이 두 테이블을
# 나란히 투영해 양안 판정 재료를 낸다. **recipe 스테이지 기본 = race981**(L-B user 판정
# 2026-07-20 — recipe.py 가 `_CALIBRATED_G_RANGES_RACE981` 을 소비). legacy 는 --ab
# calib 양안 비교용으로만 보존. 전환 커밋에서 특성화 골든 재동결(range·registry_version
# 필드 변경, 축 value 는 불변).
CALIB_TABLES: dict[str, dict[str, tuple[float, float]]] = {
    "legacy-sample1": _CALIBRATED_G_RANGES,
    "race981-20260720": _CALIBRATED_G_RANGES_RACE981,
}

# G 축 메타 (axis_id, name, korean, type, time_scale, description) — G01…G37 순서.
# name 은 face_axes 가 내는 키와 1:1(아래 import-time 가드가 정합 강제). value 는
# recipe 가 계산해 채우고, range 는 _CALIBRATED_G_RANGES 에서 주입한다.
G_AXES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("G01", "face_width_height_ratio", "얼굴형 (Face_Round / Face_Long)", "cont", "invariant", "얼굴 가로/세로 비율"),
    ("G02", "jaw_face_width_ratio", "하관 (Jaw_Wide / Jaw_Soft)", "cont", "invariant", "턱 라인 폭 / 얼굴 폭"),
    ("G03", "chin_angle_deg", "턱 각도", "cont", "invariant", "턱 끝 각도 (도)"),
    ("G04", "cheekbone_face_width_ratio", "광대", "cont", "invariant", "광대(zygomatic) 폭 / 얼굴 폭"),
    ("G05", "forehead_face_height_ratio", "이마 높이", "cont", "invariant", "이마 높이 / 얼굴 높이"),
    ("G06", "eye_width_ratio_L", "눈 크기 L (Eye_Size)", "cont", "invariant", "왼눈 가로 / 얼굴 폭"),
    ("G07", "eye_width_ratio_R", "눈 크기 R (Eye_Size)", "cont", "invariant", "오른눈 가로 / 얼굴 폭"),
    ("G08", "eye_height_ratio_L", "눈 세로 L", "cont", "invariant", "왼눈 세로 / 가로"),
    ("G09", "eye_height_ratio_R", "눈 세로 R", "cont", "invariant", "오른눈 세로 / 가로"),
    ("G10", "eye_aspect_L", "눈 종횡비 L", "cont", "invariant", "왼눈 aspect (= G08과 동일, spec 호환용)"),
    ("G11", "eye_aspect_R", "눈 종횡비 R", "cont", "invariant", "오른눈 aspect"),
    ("G12", "inter_eye_face_width_ratio", "눈 거리 (Eye_Spacing)", "cont", "invariant", "양쪽 눈 중심 간 거리 / 얼굴 폭"),
    ("G13", "eye_tilt_L_deg", "눈매 L (Eye_Slant)", "cont", "invariant", "왼눈 꼬리-앞머리 기울기 (도)"),
    ("G14", "eye_tilt_R_deg", "눈매 R (Eye_Slant)", "cont", "invariant", "오른눈 꼬리-앞머리 기울기 (도)"),
    ("G15", "nose_width_ratio", "코 폭", "cont", "invariant", "코 폭 / 얼굴 폭"),
    ("G16", "nose_length_ratio", "코 길이", "cont", "invariant", "코 길이 / 얼굴 높이"),
    ("G17", "nose_bridge_length_ratio", "코등 길이", "cont", "invariant", "코등 길이 / 얼굴 높이"),
    ("G18", "nose_tip_angle_deg", "코끝 각도", "cont", "invariant", "코끝 뾰족함 각도"),
    ("G19", "upper_lip_thickness_ratio", "윗입술 두께", "cont", "invariant", "윗입술 두께 / 얼굴 높이"),
    ("G20", "lower_lip_thickness_ratio", "아랫입술 두께", "cont", "invariant", "아랫입술 두께 / 얼굴 높이"),
    ("G21", "mouth_width_ratio", "입 (Mouth_Width)", "cont", "invariant", "입꼬리 간 거리 / 얼굴 폭"),
    ("G22", "mouth_corner_angle_deg", "입꼬리 각도", "cont", "invariant", "입 중심선 대비 입꼬리 기울기 (도)"),
    ("G23", "philtrum_length_ratio", "인중 길이", "cont", "invariant", "코 아래 → 윗입술 / 얼굴 높이"),
    ("G24", "face_thirds_balance", "얼굴 3등분 균형", "cont", "invariant", "이마/중간/턱 3분할 균형도"),
    ("G25", "face_symmetry_score", "얼굴 대칭도", "cont", "invariant", "L/R landmark 대칭"),
    ("G26", "brow_length_ratio_L", "눈썹 길이 L", "cont", "invariant", "왼눈썹 길이 / interocular"),
    ("G27", "brow_length_ratio_R", "눈썹 길이 R", "cont", "invariant", "오른눈썹 길이 / interocular"),
    ("G28", "brow_thickness_ratio_L", "눈썹 두께 L", "cont", "invariant", "왼눈썹 세로 두께 / interocular"),
    ("G29", "brow_thickness_ratio_R", "눈썹 두께 R", "cont", "invariant", "오른눈썹 세로 두께 / interocular"),
    ("G30", "brow_arch_height_L", "눈썹 아치 L", "cont", "invariant", "왼눈썹 아치 높이 / 길이"),
    ("G31", "brow_arch_height_R", "눈썹 아치 R", "cont", "invariant", "오른눈썹 아치 높이 / 길이"),
    ("G32", "brow_slope_L_deg", "눈썹 기울기 L", "cont", "invariant", "왼눈썹 inner→outer 기울기 (도)"),
    ("G33", "brow_slope_R_deg", "눈썹 기울기 R", "cont", "invariant", "오른눈썹 기울기 (도)"),
    ("G34", "brow_eye_distance_ratio", "눈썹-눈 거리", "cont", "invariant", "(L/R 평균) brow → eye / face_height"),
    ("G35", "inter_brow_distance_ratio", "미간", "cont", "invariant", "양 눈썹 inner 사이 거리 / 얼굴 폭"),
    ("G36", "chin_length_ratio", "턱 길이 (Chin_Length)", "cont", "invariant", "입 중심 → 턱 끝 / 얼굴 높이"),
    ("G37", "mouth_corner_class", "입꼬리 분류 (Mouth_Corner)", "cat", "invariant", "G22 기반 3-class (low<-3°, mid -3~+5°, high>+5°)"),
)

# 미충전 축 (momentscan 이 오늘 안 재는 카테고리) — unfilled 보고용 ID 목록, 순서 보존.
# 라벨/range 없이 ID·카테고리명만: 이 축들엔 아직 값 소비자가 없다(정직한 결측).
UNFILLED_AXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Color/Texture Body", ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10")),
    ("Hair", ("H01", "H02", "H03", "H04", "H05", "H06", "H07", "H08", "H09", "H10", "H11", "H12", "H13", "H14", "H15")),
    ("Accessories", ("A01", "A02", "A03", "A04", "A05", "A06")),
    ("Semantic (privacy-sensitive)", ("S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10")),
    ("Wear (Clothing & Color Identity)", ("W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08", "W09", "W10")),
)

# import-time 드리프트 가드: 공식(face_axes)이 내는 키 집합 == 정책(여기)이 라벨하는
# 키 집합. 한쪽만 축을 추가/개명하면 프로세스가 뜨기 전에 시끄럽게 죽는다(code-style §3a).
_G_NAMES = frozenset(name for _id, name, *_ in G_AXES)
assert _G_NAMES == frozenset(AXIS_NAMES), (
    "face_axes.AXIS_NAMES ⇄ recipe_axes.G_AXES 드리프트: "
    f"{_G_NAMES ^ frozenset(AXIS_NAMES)}")
