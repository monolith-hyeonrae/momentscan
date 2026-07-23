"""샘플링 워크벤치 v0.12 (2026-07-23) — 원장 ⑪⑫ 계기. 참조 구현(콘솔 파리티의 정본).

v0.18 **패턴 축(볼빛−턱그늘)**(user 2026-07-23 "빛이 들어오는 부위별 차등 — 볼 삼각형
=밝게·턱 후방 경계=그늘"): pattern=(볼 8점 가중휘도 − 턱후방 6점 가중휘도)/얼굴평균
— 프레임-내 스킨-영역 대비+정규화로 albedo 대체 소거(사진 조명 문법: 렘브란트/루프
계열; dp[방향 존재량]의 영역-해상 진화형; SH-시그니처 매칭은 SH 검증 후 2안). 풀-내
pct, 빛 채널 4번째 세부(pa_min 기본 off=셀프테스트 불변). 마스크 오버레이에 영역
마커(볼=청록·턱=주황) — 영역 인덱스 자가 검증.
v0.17 **빛 계기 투명화**(user: "스킨마스크 범위와 32×32 맵을 보고 싶다"): 검사 뷰
빛 모드에 ①skin 마스크 재현 오버레이(전 행 — 앵커 20·타원 hull 36·눈꼬리 2 좌표
선적, hull 클립+가우시안 σ=0.16 IOD) ②32×32 광량 맵 재현(bbox 크롭→그레이→5탭
블러, 픽셀 확대)+**lr/tb 즉석 재계산 vs 저장값 대조**(재현-일치 검증) ③lt 성분 분해
(휘도 pct+색량 pct, v0.16.1). 재현=224px 썸네일 근사 — 큰 어긋남만 의미.
v0.16 타임라인 sticky+결과/풀 박스 분리 · v0.15 **데크 좌측 이동**(user): 하단 →
좌측 사이드바(384px, 탭→브리지→트리→가로 페이더 세로 스택). 본문·검사 패널 배치 불변.
v0.14 채널 탭 내 **트리 구조**: 세부 채널 타이틀(1열·가지선)+다이얼, 밴드=한 세부
채널에 2다이얼(yaw 하한/상한·ex 밴드).
v0.13 **채널 탭 데크 + 미터 브리지 + 접이식 검사 패널**(user: "가로 스트립=조잡, 탭
분리 + 검사 접이식"): 데크=탭당 채널 하나(다이얼 전폭 2열 그리드+대형 분포 미터,
세로 페이더) · 탭에 S/M 미니 버튼(뮤트 탭=흐림) · 탭 선택=검사 뷰 모드 동기화 ·
**미터 브리지**(탭 바 우측 — 선택 프레임의 채널별 상태점수 가로 막대, 전 채널 상시
판독 유지) · 검사 패널 ◀▶ 핸들로 접기(데크·본문이 전폭 확장). 데크 높이 248px.
v0.12 콘솔 데크(가로 스트립) — v0.13으로 대체. 로직·데이터 불변(HTML-only).

v0.11 **축 solo/mute — 믹싱 콘솔 문법**(mb-wbsolo, 검증 2층 구조의 1층 도구): 상태
그룹 헤더에 [S][M] — mute=그 채널의 하드 게이트 해제+소프트 가중 0(다이얼 값은 보존,
오버라이드만) · solo=나머지 일괄 mute(재클릭=해제) · 뮤트 중엔 "믹스(뮤트 해제) 픽"
참조 행 표시 = solo-선택 vs 종합-선택 diff(1층→2층 다리). 뮤트는 시뮬 전용(셀프테스트
=뮤트 없음 기본에서만; 파이썬 미러 불변). 전 가중 0(예: 포즈 solo)이면 픽=밴드 내
시간순 — 중립 폴백.

v0.10 **상태 검사 뷰 + 3열 골격**(user: "다이얼마다 서로 다른 분석 시각화 — 빛=SH가
얼굴에 그리는 조명, 포즈=오버레이로 추정 검증"): 좌=다이얼(상태 아코디언·조작 시
해당 상태 모드로 자동 전환) / 중=타임라인+픽+풀 / 우=**상태 검사 패널**(선택 프레임
큰 이미지 + 모드별 렌더). 검사 모드: 포즈=랜드마크 와이어+ypr(픽 프레임 한정 선적,
전 프레임은 콘솔 온디맨드 확장 예정) · 표정=blendshape 상위 막대(픽 한정)+pu/ex ·
빛=**SH 구면 렌더**(face_sh_0..8, DPR 9계수→JS 실시간)+lr/tb 방향 화살표 · 영상=
Laplacian 선명 히트맵(픽 한정 사전렌더) · 왜곡=cs/mv 시계열 궤적+선택 마커.
**클릭 의미 변경**: 클릭=프레임 선택(검사 패널 갱신) · GT=검사 패널의 ＋/−/지움
버튼(오클릭 방지) · Shift+클릭=포즈 그라운딩 유지.

v0.9 상태-쿼리: 1단=상태별 스크린/밴드(포즈=밴드가 곧 쿼리·표정 ex_min~ex_max 밴드)
· 2단=상태 점수 4종 종합(얼굴=(2무표정+눈동자)/3·빛=조도생동[×lf]·영상=(선명+micro)/2
·왜곡=(cs+입가시+norm)/3) — v7.2 브리지 종료, 가드=JS≡python 셀프테스트.
v0.8 빛 판별력 lf(+분산-감쇠 ATT 토글) · v0.7 상태 5그룹(퍼널·타임라인 5색) ·
v0.6 공평 우주(전 행 썸네일·유령 레인·축=0..vf) · v0.5 yaw 부호-밴드 ·
v0.4 다이얼 분포 지도 · v0.3 포즈 그라운딩·pitch · v0.2 타임라인 · v0.1 단일-클립 탭.
층: frame_table(stash 읽기-전용 파생) + 시뮬레이터 + 클릭 GT(fixtures/eval, workbench-gt/v0).
승격(track/lk-workbench): 정식 표면 = momentscan workbench — 이 스크립트가 값-동일 참조 구현.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from mediapipe.tasks.python.vision.face_landmarker import (
    FaceLandmarksConnections as _FLC,
)

from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.perception.readings.geometry import canonicalize
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX
from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

from scratchpad_likeness_sat import skin_sv

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
CLIPS = ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1")
THUMB = 224     # 저장 원치수 — 픽 행은 원치수, 풀은 112 축소 표시+호버 확대
EDGES = [[c.start, c.end] for c in (*_FLC.FACE_LANDMARKS_CONTOURS, *_FLC.FACE_LANDMARKS_NOSE)]

# 검사 뷰(빛) — skin 마스크 재현용: parse._quality와 동일 상수
SKIN_ANCHORS = (9, 107, 336, 151, 67, 297, 50, 280, 205, 425, 116, 345, 123, 352,
                152, 175, 200, 6, 197, 195)
EYE_CORNERS = (33, 263)
# v0.18 패턴 축(user 2026-07-23: 볼빛−턱그늘) — 영역 정의(오버레이로 자가 검증)
CHEEK_PTS = (50, 205, 116, 123, 280, 425, 345, 352)     # 눈아래 볼 삼각형(양측)
JAW_PTS = (132, 58, 172, 361, 288, 397)                 # 턱 후방 경계(하악각 부근, 양측)


def _oval_order():
    """FACE_OVAL 연결쌍을 체인 순서로 — hull 폴리곤 경로용."""
    conns = {c.start: c.end for c in _FLC.FACE_LANDMARKS_FACE_OVAL}
    start = next(iter(conns))
    seq = [start]
    while len(seq) <= len(conns):
        nxt = conns.get(seq[-1])
        if nxt is None or nxt == start:
            break
        seq.append(nxt)
    return seq


OVAL_ORDER = _oval_order()

# 기본 설정 — JS DEF와 문자 그대로 동일해야 함 (셀프테스트 = JS≡python 가드)
DEFAULT_CFG = {"sym_max": 0.6, "dev_lo": -15.0, "dev_hi": 15.0, "pt_max": 99.0, "pu_min": 0.4,
               "cs_min": 0.0, "mv_min": 0.0, "lt_min": 0.0, "ex_min": 0.0, "ex_max": 1.0,
               "gap_min": 12, "dp_min": 0.0, "hh_max": 100.0, "sp_min": 0.0, "pa_min": 0.0,
               "w_face": 0.45, "w_light": 0.20, "w_image": 0.15, "w_distort": 0.20}


def state_scores(r):
    """상태 점수 4종 — r=[무표정,눈동자,선명,micro,norm,cs,입가시,빛] rank01."""
    re_, rp_, rs_, rm_, rn_, rc_, rv_, rl_ = r
    return ((2 * re_ + rp_) / 3, rl_, (rs_ + rm_) / 2, (rc_ + rv_ + rn_) / 3)


def face_signals(P):
    def d2(a, b):
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)
    r_iris = (d2(469, 471) + d2(470, 472)) / 2 + 1e-9
    l_iris = (d2(474, 476) + d2(475, 477)) / 2 + 1e-9
    pupil = (d2(159, 145) / r_iris + d2(386, 374) / l_iris) / 2
    dr = np.abs(P[:, 1, 0] - P[:, 234, 0]) + 1e-9
    dl = np.abs(P[:, 454, 0] - P[:, 1, 0]) + 1e-9
    return pupil, np.abs(np.log(dr / dl))


def pct_rank(x):
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def rank01(x, flip=False):
    r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
    r = r / max(len(x) - 1, 1)
    return 1 - r if flip else r


def frame_table(clip_id: str, out_root: Path):
    """클립 main rider의 전 신호 와이드 테이블 (+유령 우주·검사 뷰 컨텍스트)."""
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    lmr = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    lm_all_cb = {int(f): tuple(float(v) for v in b)
                 for f, b in zip(lmr["frame_idx"].to_list(), lmr["crop_box"].to_list())}
    gt = pl.read_parquet(out_root / clip_id / "gate_trace.parquet").filter(pl.col("track_id") == tid)
    valid = set(gt.filter(pl.col("valid"))["frame_idx"].to_list())
    lm = lmr
    keep = lm["frame_idx"].is_in(list(valid))
    if int(keep.sum()) >= 10:
        lm = lm.filter(keep)
    fx = lm["frame_idx"].to_numpy()
    n = len(fx)
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(n, 478, 3)
    T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(n, 4, 4)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    canonicalize(P, T, cb)

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    pitch = M[sel, INDEX["head_pitch"]]
    roll = M[sel, INDEX["head_roll"]]
    blur = M[sel, INDEX["face_blur"]]
    light_lr = M[sel, INDEX["face_light_lr"]]
    light_tb = M[sel, INDEX["face_light_tb"]]
    light_hh = M[sel, INDEX["face_light_harsh"]]
    SH = np.stack([M[sel, INDEX[f"face_sh_{k}"]] for k in range(9)], axis=1)   # 검사 뷰(빛)

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    g = lambda col: (dict(zip(pq["frame_idx"].to_list(), pq[col].to_list())) if col in pq.columns else {})
    micro_of, mv_of, lum_of, hi_of = g("face_micro"), g("mouth_vis"), g("skin_lum"), g("skin_clip_hi")
    micro = np.array([micro_of.get(int(f), np.nan) for f in fx], float)
    mv = np.array([mv_of.get(int(f), np.nan) for f in fx], float)
    lum = np.array([lum_of.get(int(f), np.nan) for f in fx], float)
    chi = np.array([hi_of.get(int(f), np.nan) for f in fx], float)
    lum_eff = lum * (1.0 - np.nan_to_num(chi, nan=0.0))

    det_all = pl.read_parquet(out_root / clip_id / "detections.parquet")
    det = det_all.filter(pl.col("track_id") == tid)
    det_bbox = {int(f): tuple(float(v) for v in b)
                for f, b in zip(det["frame_idx"].to_list(), det["bbox"].to_list()) if b is not None}
    frag_bbox = {}
    if "subject_id" in det_all.columns:
        sids = det["subject_id"].drop_nulls().unique().to_list()
        if sids:
            fr = det_all.filter(pl.col("subject_id").is_in(sids) & (pl.col("track_id") != tid))
            frag_bbox = {int(f): tuple(float(v) for v in b)
                         for f, b in zip(fr["frame_idx"].to_list(), fr["bbox"].to_list()) if b is not None}
    erows = [(int(f), np.asarray(e, float)) for f, e in
             zip(det["frame_idx"].to_list(), det["embedding"].to_list()) if e is not None]
    cs = np.full(n, np.nan)
    nrm = np.full(n, np.nan)
    if len(erows) >= 10:
        dfr = np.array([f for f, _ in erows])
        dE = np.stack([e for _, e in erows])
        dn = np.linalg.norm(dE, axis=1)
        Eh = dE / dn[:, None]
        c0 = np.median(Eh, axis=0)
        c0 /= np.linalg.norm(c0)
        cs_of = dict(zip(dfr.tolist(), (Eh @ c0).tolist()))
        nm_of = dict(zip(dfr.tolist(), dn.tolist()))
        cs = np.array([cs_of.get(int(f), np.nan) for f in fx])
        nrm = np.array([nm_of.get(int(f), np.nan) for f in fx])

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    ph = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([ph.get(int(f)) == "boarding" for f in fx])

    B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
    ecols = [i for i, nm_ in enumerate(BLENDSHAPE_ORDER)
             if nm_ != "_neutral" and not nm_.startswith("eyeLook")]
    expr = B[:, ecols].max(axis=1)
    pupil, sym = face_signals(P)
    return dict(tid=tid, rider=rider, fx=fx, cb=cb, P=P, yaw=yaw, pitch=pitch, roll=roll,
                blur=blur, micro=micro, mv=mv, lum_eff=lum_eff, cs=cs, nrm=nrm, board=board,
                expr=expr, pupil=pupil, sym=sym, lm_all_cb=lm_all_cb, det_bbox=det_bbox,
                frag_bbox=frag_bbox, light_lr=light_lr, light_tb=light_tb, light_hh=light_hh,
                SH=SH, B=B)


def compute_picks(rows, cfg):
    """JS 시뮬레이터와 문자 그대로 동일한 의미론 (반올림된 shipped 값 위에서)."""
    surv = [r for r in rows
            if r["sy"] < cfg["sym_max"] and cfg["dev_lo"] < r["dv"] < cfg["dev_hi"]
            and abs(r["pc"]) < cfg["pt_max"]
            and r["pu"] >= cfg["pu_min"]
            and (r["cs"] is None or r["cs"] >= cfg["cs_min"])
            and (r["mv"] is None or r["mv"] >= cfg["mv_min"])
            and (r["lt"] is None or r["lt"] >= cfg["lt_min"])
            and (r["dp"] is None or r["dp"] >= cfg["dp_min"])
            and (r["pa"] is None or r["pa"] >= cfg["pa_min"])
            and (r["hh"] is None or r["hh"] <= cfg["hh_max"])
            and (r["sp"] is None or r["sp"] >= cfg["sp_min"])
            and cfg["ex_min"] <= r["ex"] <= cfg["ex_max"]]
    for r in surv:
        sf, sl, si, sd = state_scores(r["r"])
        r["_s"] = (cfg["w_face"] * sf + cfg["w_light"] * sl
                   + cfg["w_image"] * si + cfg["w_distort"] * sd)
    surv.sort(key=lambda r: -r["_s"])
    got = []
    for r in surv:
        if all(abs(r["f"] - o["f"]) >= cfg["gap_min"] for o in got):
            got.append(r)
        if len(got) == 3:
            break
    return [r["f"] for r in got]


def build_clip(clip_id, out_root, wb_dir):
    t = frame_table(clip_id, out_root)
    fx, cb, P = t["fx"], t["cb"], t["P"]
    n = len(fx)

    dev = t["yaw"] - FRONTAL_DEG
    cur = [f for f in t["rider"]["samples"]["center_nearest"]]
    bins = t["rider"]["samples"].get("pose_bins", {})
    row_of = {int(f): i for i, f in enumerate(fx)}
    fxset = set(row_of)
    inv_f = sorted(set(t["lm_all_cb"]) - fxset)
    det_f = sorted(set(t["det_bbox"]) - set(t["lm_all_cb"]))
    frag_f = sorted(set(t["frag_bbox"]) - set(t["det_bbox"]) - set(t["lm_all_cb"]))
    ghost_kind = {**{f: "inv" for f in inv_f}, **{f: "det" for f in det_f},
                  **{f: "frag" for f in frag_f}}
    ghost_thumb = set()
    for kfs in (inv_f, det_f, frag_f):
        if len(kfs) > 60:
            ghost_thumb |= {kfs[i] for i in np.unique(np.linspace(0, len(kfs) - 1, 60).astype(int))}
        else:
            ghost_thumb |= set(kfs)

    def _sq(b, W0, H0, pad=1.3):
        x1, y1, x2, y2 = b
        cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * pad / 2
        return max(0, int(cx - s)), max(0, int(cy - s)), min(W0, int(cx + s)), min(H0, int(cy + s))

    def _region_lum(gray, p, idxs, sig):
        """영역 가중 휘도 — 지정 랜드마크들의 가우시안 가중 평균 (마스크와 동일 기법)."""
        h2, w2 = gray.shape
        yy, xx = np.mgrid[0:h2, 0:w2]
        wgt = np.zeros((h2, w2), np.float32)
        for j in idxs:
            ax, ay = p[j]
            wgt += np.exp(-((xx - ax) ** 2 + (yy - ay) ** 2) / (2.0 * sig * sig))
        m = wgt.ravel() > 1e-3
        if m.sum() < 20:
            return np.nan
        wf, vf_ = wgt.ravel()[m], gray.ravel()[m]
        return float((vf_ * wf).sum() / wf.sum())

    chroma = np.full(n, np.nan)
    pat = np.full(n, np.nan)     # v0.18 패턴: (볼빛 − 턱그늘)/얼굴평균
    tdir = wb_dir / "thumbs" / clip_id
    tdir.mkdir(parents=True, exist_ok=True)
    thumb_ok = set()
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    vf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fidx = 0
    while True:
        ok, frm = cap.read()
        if not ok:
            break
        H0, W0 = frm.shape[:2]
        i = row_of.get(fidx)
        box = None
        if i is not None:
            cbv = cb[i]
            pts = np.stack([cbv[0] + P[i, :, 0] * (cbv[2] - cbv[0]),
                            cbv[1] + P[i, :, 1] * (cbv[3] - cbv[1])], 1)
            r = skin_sv(frm, pts, cbv)
            if r is not None:
                chroma[i] = r[3]
                x1c, y1c = max(0, int(cbv[0])), max(0, int(cbv[1]))
                x2c, y2c = min(W0, int(cbv[2])), min(H0, int(cbv[3]))
                if x2c - x1c > 8 and y2c - y1c > 8:
                    sub_g = cv2.cvtColor(frm[y1c:y2c, x1c:x2c], cv2.COLOR_BGR2GRAY).astype(np.float32)
                    p_sub = pts - np.array([x1c, y1c], np.float64)
                    iod = np.linalg.norm(p_sub[33] - p_sub[263]) + 1e-6
                    sig = 0.16 * iod
                    cl = _region_lum(sub_g, p_sub, CHEEK_PTS, sig)
                    jl = _region_lum(sub_g, p_sub, JAW_PTS, sig * 0.7)
                    if np.isfinite(cl) and np.isfinite(jl) and r[2] > 1:
                        pat[i] = (cl - jl) / (r[2] + 1e-6)   # r[2]=v_mean(얼굴 평균 명도)
            box = tuple(cbv)
        elif fidx in ghost_thumb:
            k = ghost_kind[fidx]
            box = (t["lm_all_cb"].get(fidx) if k == "inv"
                   else _sq(t["det_bbox"].get(fidx) or t["frag_bbox"].get(fidx), W0, H0))
        if box is not None:
            x1, y1, x2, y2 = (int(v) for v in box)
            if x2 - x1 > 1 and y2 - y1 > 1:
                tile = cv2.resize(frm[max(0, y1):y2, max(0, x1):x2], (THUMB, THUMB))
                cv2.imwrite(str(tdir / f"f{fidx:05d}.jpg"), tile,
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
                thumb_ok.add(fidx)
        fidx += 1
    cap.release()
    vf = max(vf, fidx)
    covered = fxset | set(ghost_kind)
    absent = []
    _st = None
    for f in range(vf):
        if f not in covered:
            if _st is None:
                _st = f
        elif _st is not None:
            absent.append([_st, f - 1])
            _st = None
    if _st is not None:
        absent.append([_st, vf - 1])
    ghost = [{"f": f, "k": k,
              "th": (f"thumbs/{clip_id}/f{f:05d}.jpg" if f in thumb_ok else None)}
             for f, k in sorted(ghost_kind.items())]

    micro_pct, sharp_pct = pct_rank(t["micro"]), pct_rank(t["blur"])
    norm_pct, cs_pct, mv_pct = pct_rank(t["nrm"]), pct_rank(t["cs"]), pct_rank(t["mv"])
    lum_pct, ch_pct = pct_rank(t["lum_eff"]), pct_rank(chroma)   # lt 성분 분해(1층 판독용)
    light_pct = np.nanmean(np.vstack([lum_pct, ch_pct]), axis=0)
    pat_pct = pct_rank(pat)                                       # v0.18 패턴(볼빛−턱그늘)
    dp_pct = pct_rank(np.abs(t["light_lr"]) + np.abs(t["light_tb"]))
    hh_pct = pct_rank(t["light_hh"])

    def _spread(v):
        fin = v[np.isfinite(v)]
        if len(fin) < 10:
            return 0.0
        p10, p50, p90 = np.percentile(fin, [10, 50, 90])
        return float((p90 - p10) / (abs(p50) + 1e-6))
    lf = round(min(1.0, 0.5 * (_spread(t["lum_eff"]) + _spread(chroma)) / 0.8), 2)

    R = np.stack([rank01(t["expr"], flip=True), rank01(t["pupil"]),
                  rank01(sharp_pct), rank01(micro_pct), rank01(norm_pct),
                  rank01(cs_pct), rank01(mv_pct), rank01(light_pct)], axis=1)

    def num(v, nd=2):
        return None if not np.isfinite(v) else round(float(v), nd)

    pt = t["pitch"]
    pt_med = float(np.nanmedian(pt)) if np.isfinite(pt).any() else 0.0

    def _pts(i, idxs):
        return [[round(float(P[i, j, 0]), 3), round(float(P[i, j, 1]), 3)] for j in idxs]

    def _bb(i):
        b = t["det_bbox"].get(int(fx[i]))
        if b is None:
            return None
        cbv = cb[i]
        w, hgt = max(cbv[2] - cbv[0], 1e-6), max(cbv[3] - cbv[1], 1e-6)
        return [round(max(0.0, min(1.0, (b[0] - cbv[0]) / w)), 3),
                round(max(0.0, min(1.0, (b[1] - cbv[1]) / hgt)), 3),
                round(max(0.0, min(1.0, (b[2] - cbv[0]) / w)), 3),
                round(max(0.0, min(1.0, (b[3] - cbv[1]) / hgt)), 3)]

    rows = []
    for i in range(n):
        sh_i = t["SH"][i]
        rows.append({"f": int(fx[i]), "b": int(t["board"][i]),
                     "pt": num(pt[i], 1),
                     "pc": round(float(pt[i] - pt_med), 1) if np.isfinite(pt[i]) else 0.0,
                     "rl": num(t["roll"][i], 1),
                     "lr": num(t["light_lr"][i], 3), "tb": num(t["light_tb"][i], 3),
                     "sh": ([round(float(v), 3) for v in sh_i] if np.isfinite(sh_i).all() else None),
                     "sy": round(float(t["sym"][i]), 3) if np.isfinite(t["sym"][i]) else 9.9,
                     "dv": round(float(dev[i]), 1) if np.isfinite(dev[i]) else 99.0,
                     "pu": round(float(t["pupil"][i]), 3) if np.isfinite(t["pupil"][i]) else 0.0,
                     "ex": round(float(t["expr"][i]), 3) if np.isfinite(t["expr"][i]) else 1.0,
                     "cs": num(cs_pct[i], 1), "mv": num(mv_pct[i], 1), "lt": num(light_pct[i], 1),
                     "lm": num(lum_pct[i], 1), "ch": num(ch_pct[i], 1),
                     "dp": num(dp_pct[i], 1), "hh": num(hh_pct[i], 1), "sp": num(sharp_pct[i], 1),
                     "pa": num(pat_pct[i], 1), "par": num(pat[i], 3),
                     "r": [round(float(v), 4) for v in R[i]],
                     "sk": {"a": _pts(i, SKIN_ANCHORS), "o": _pts(i, OVAL_ORDER),
                            "e": _pts(i, EYE_CORNERS), "c": _pts(i, CHEEK_PTS),
                            "j": _pts(i, JAW_PTS)},
                     "bb": _bb(i),
                     "th": (f"thumbs/{clip_id}/f{int(fx[i]):05d}.jpg" if int(fx[i]) in thumb_ok else None)})
    selftest = compute_picks([dict(r) for r in rows], DEFAULT_CFG)

    # ── 검사 뷰(픽 한정) 자산: 랜드마크 2D·blendshape 상위·Laplacian 히트맵 ──
    pickset = sorted({int(f) for f in (*cur, *selftest, *bins.values()) if int(f) in row_of})
    pv = {}
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    for f in pickset:
        i = row_of[f]
        lm2 = [[round(float(x), 3), round(float(y), 3)] for x, y in P[i, :, :2]]
        bs_row = t["B"][i]
        top = np.argsort(-bs_row)
        bs_top = [[BLENDSHAPE_ORDER[j], round(float(bs_row[j]), 3)]
                  for j in top if BLENDSHAPE_ORDER[j] != "_neutral"][:8]
        lap_ok = 0
        cbv = cb[i]
        x1, y1, x2, y2 = (int(v) for v in cbv)
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frm = cap.read()
        if ok and x2 - x1 > 1 and y2 - y1 > 1:
            gray = cv2.cvtColor(frm[max(0, y1):y2, max(0, x1):x2], cv2.COLOR_BGR2GRAY)
            lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
            hi = np.percentile(lap, 99) + 1e-6
            lapu = np.clip(lap / hi * 255, 0, 255).astype(np.uint8)
            cv2.imwrite(str(tdir / f"f{f:05d}_lap.jpg"),
                        cv2.resize(lapu, (THUMB, THUMB)), [cv2.IMWRITE_JPEG_QUALITY, 80])
            lap_ok = 1
        pv[str(f)] = {"lm": lm2, "bs": bs_top, "rl": num(t["roll"][i], 1), "lap": lap_ok}
    cap.release()

    return {"clip": clip_id, "tid": t["tid"], "n": n, "vf": vf, "cur": cur, "lf": lf,
            "selftest": selftest, "rows": rows, "ghost": ghost, "absent": absent, "pv": pv}


HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>likeness sampling workbench v0.10</title>
<style>
body{background:#161616;color:#ddd;font:13px/1.45 system-ui,sans-serif;margin:0}
#top{position:sticky;top:0;background:#1d1d1d;border-bottom:1px solid #333;padding:8px 14px;z-index:9}
#selftest{font-weight:600}
.ok{color:#7c6} .bad{color:#e66}
#insp{position:fixed;right:0;top:78px;bottom:0;width:340px;overflow:auto;background:#1b1b1b;
  border-left:1px solid #333;padding:10px 12px;box-sizing:border-box;z-index:8}
#deck{position:fixed;left:0;top:78px;bottom:0;width:384px;background:#191919;
  border-right:2px solid #3a3a3a;padding:8px 12px;box-sizing:border-box;z-index:8;overflow-y:auto}
#dtabs{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.dtab{padding:3px 12px;border:1px solid #444;border-radius:4px 4px 0 0;cursor:pointer;
  font-size:12px;color:#aaa;display:flex;align-items:center;gap:6px}
.dtab.cur{background:#262f38;color:#dfeaf5;border-color:#6a92b8;font-weight:600}
.dtab.dm{opacity:.45}
.dtab .sm{font-size:9px;border:1px solid #555;border-radius:2px;padding:0 4px;color:#999}
.dtab .sm.on{color:#161616;font-weight:700}
.dtab .sm.s.on{background:#d8c455;border-color:#d8c455}
.dtab .sm.m.on{background:#e06666;border-color:#e06666}
#bridge{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:4px 0 8px;
  padding-bottom:6px;border-bottom:1px solid #2c2c2c}
.bm{font-size:10px;color:#889}
.bm .bar{display:inline-block;width:44px;height:8px;background:#141414;border:1px solid #2c2c2c;
  vertical-align:middle;margin-left:4px}
.bm .bar i{display:block;height:100%}
.chanview{display:block}
.chanview .body{display:block}
.chanview .dial{margin:4px 0 8px}
.chanview .dial label{font-size:12.5px}
.chanview.gmuted .body{opacity:.4}
.subch{border-left:2px solid #3a4a5a;margin:6px 0 10px 4px;padding-left:12px}
.subttl{font-size:12px;font-weight:600;color:#9ad;margin-bottom:2px}
.fblock{display:flex;gap:10px;align-items:center;padding:8px 4px 0;border-top:1px solid #2c2c2c;
  margin-top:8px}
.fader{flex:1;display:flex;gap:8px;align-items:center}
.fader input{flex:1}
.fader .fv{font-size:12px;color:#fc6;min-width:34px;text-align:right}
.mlbl{font-size:10px;color:#777}
#inspToggle{position:fixed;right:340px;top:84px;z-index:12;background:#2a2a2a;border:1px solid #555;
  color:#bbb;border-radius:3px 0 0 3px;cursor:pointer;padding:4px 5px;font-size:11px}
body.inspc #inspToggle{right:0}
body.inspc #insp{display:none}
body.inspc #main{margin-right:30px}
#main{margin-left:384px;margin-right:340px;margin-bottom:20px;padding:10px 16px}
#sticky{position:sticky;top:78px;background:#161616;z-index:5;padding:4px 0 6px;
  border-bottom:1px solid #2c2c2c}
.box{border:1px solid #2a2a2a;border-radius:6px;padding:10px 14px;margin:14px 0;background:#191919}
.box .boxttl{font-size:12px;font-weight:600;color:#9ad;margin-bottom:6px}
.grp{margin:10px 0 4px;color:#9ad;font-weight:600;font-size:12px;text-transform:uppercase;cursor:pointer;
  display:flex;align-items:center;gap:6px}
.grp .arr{color:#678}
.grp .sm{font-size:10px;border:1px solid #555;border-radius:2px;padding:0 5px;color:#999;cursor:pointer}
.grp .sm.on{color:#161616;font-weight:700}
.grp .sm.s.on{background:#d8c455;border-color:#d8c455}
.grp .sm.m.on{background:#e06666;border-color:#e06666}
.gmute{opacity:.35}
.dial{margin:6px 0}
.dial label{display:flex;justify-content:space-between;font-size:12px;color:#bbb}
.dial.mod label{color:#fc6}
.dial.mod label::after{content:" •"}
.dial input[type=range]{width:100%}
.dh{display:block;background:#141414;border:1px solid #2e2e2e;margin-top:1px}
#tabs{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 10px}
.tab{padding:4px 10px;border:1px solid #444;border-radius:4px;cursor:pointer;font-size:12px;color:#aaa}
.tab.cur{background:#28343f;color:#dfeaf5;border-color:#6a92b8}
.tab .b{color:#9a8} .tab .g{color:#cb8}
.funnel{margin:6px 0 10px;max-width:560px}
.fr{display:flex;align-items:center;gap:8px;font-size:11px;color:#9a8;margin:1px 0}
.fr .lbl{width:52px;text-align:right;color:#8b9}
.fr .bar{height:9px;border-radius:2px}
.fr .cnt{color:#bcb}
.rowlbl{color:#89b;font-size:11px;margin-top:12px}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
.cell{position:relative;cursor:pointer}
.strip.sm .cell,.strip.sm .cell img,.strip.sm .cell .noimg{width:112px}
.strip.sm .cell img,.strip.sm .cell .noimg{height:112px}
.strip.big .cell,.strip.big .cell img,.strip.big .cell .noimg{width:224px}
.strip.big .cell img,.strip.big .cell .noimg{height:224px}
.cell img{display:block;border:2px solid #444;box-sizing:border-box;transition:transform .07s}
.strip.sm .cell:hover img{transform:scale(2);position:relative;z-index:8;border-color:#9cf}
.strip.big .cell:hover img{transform:scale(1.4);position:relative;z-index:8;border-color:#9cf}
.cell .noimg{border:2px dashed #444;box-sizing:border-box;display:flex;align-items:center;
  justify-content:center;color:#666;font-size:10px}
.cell .cap{font-size:10px;color:#aaa;line-height:1.25;margin-top:1px}
.cell.pos img,.cell.pos .noimg{border-color:#5c5}
.cell.neg img,.cell.neg .noimg{border-color:#e55}
.cell.selg img{box-shadow:0 0 0 2px #f90}
.cell .flag{position:absolute;top:2px;right:2px;font-size:12px;color:#fff;text-shadow:0 0 3px #000}
.pickA img{outline:2px solid #7ac} .pickB img{outline:2px dashed #ca7}
.diff img{outline-color:#f80 !important}
#tl{position:relative;margin:8px 0 2px;max-width:1004px}
#tl canvas{display:block;background:#101010;border:1px solid #333;cursor:crosshair}
#tlTip{position:absolute;display:none;background:#222;border:1px solid #555;padding:4px;
  z-index:20;pointer-events:none;font-size:10px;color:#ccc;line-height:1.3}
#tlTip img{width:112px;height:112px;display:block;border:1px solid #444;margin-bottom:2px}
.legend{font-size:10px;color:#999;margin:2px 0 10px}
.legend span{display:inline-block;margin-right:11px}
.legend i{display:inline-block;width:9px;height:9px;margin-right:3px;vertical-align:-1px}
.itabs{display:flex;gap:4px;flex-wrap:wrap;margin:6px 0}
.itab{padding:2px 8px;border:1px solid #444;border-radius:3px;cursor:pointer;font-size:11px;color:#aaa}
.itab.cur{background:#3a3226;color:#fc6;border-color:#a86}
#inspImg{width:300px;height:300px;display:block;border:1px solid #444;background:#111}
.ibar{display:flex;align-items:center;gap:6px;font-size:11px;margin:2px 0}
.ibar .nm{width:130px;color:#aab;text-align:right;overflow:hidden;white-space:nowrap}
.ibar .bv{height:9px;background:#7a9ac0}
.gtbtn button{margin-right:6px}
button{background:#2a2a2a;color:#ddd;border:1px solid #555;border-radius:3px;
  padding:3px 10px;margin-right:6px;cursor:pointer}
button:hover{background:#383838}
.gtscore{color:#cb8;font-size:12px;margin-left:12px}
.note{color:#777;font-size:11px}
</style></head><body>
<div id="top">
 <span id="selftest">selftest…</span>
 <button onclick="snapshotB()">현재 설정 → B 저장</button>
 <button onclick="clearB()">B 지우기</button>
 <button onclick="resetA()">A 기본값</button>
 <button onclick="exportGT()">GT export (.jsonl)</button>
 <input type="file" id="gtfile" style="display:none" onchange="importGT(this)">
 <button onclick="document.getElementById('gtfile').click()">GT import</button>
 <span class="gtscore" id="gtscore"></span>
 <div class="note"><b>클릭=프레임 선택(우측 검사)</b> · GT=검사 패널 ＋/− 버튼 · Shift+클릭=포즈 그라운딩 · 호버=확대 · ←→=클립 · 저장 홈=fixtures/eval/</div>
</div>
<div id="main"></div><div id="insp"></div><div id="deck"></div>
<button id="inspToggle" onclick="document.body.classList.toggle('inspc')">◀▶</button>
<script src="data.js"></script>
<script>
const DIALS=[
 ["포즈"],
 ["sym_max","보이는-정면 sym <",0.3,2.0,0.05],
 ["dev_lo","yaw dev 하한 > (밴드)",-90,89,1],
 ["dev_hi","yaw dev 상한 < (밴드)",-89,90,1],
 ["pt_max","|pitch dev| < (클립상대·99=off)",3,99,1],
 ["표정·얼굴"],
 ["pu_min","눈동자 pupil >=",0,0.8,0.01],
 ["ex_min","표정 ex 하한 >= (밴드)",0,0.8,0.05],
 ["ex_max","표정 ex 상한 <= (밴드)",0.2,1.0,0.05],
 ["빛"],
 ["lt_min","조도·생동 lt pct >=",0,90,5],
 ["pa_min","패턴 pa pct >= (볼빛−턱그늘)",0,90,5],
 ["dp_min","입체감 dp pct >= (방향성)",0,90,5],
 ["hh_max","거칠기 hh pct <=",10,100,5],
 ["영상"],
 ["sp_min","선명 sp pct >=",0,90,5],
 ["왜곡"],
 ["cs_min","정체성 cs pct >=",0,90,5],
 ["mv_min","입-가시 mv pct >=",0,90,5],
 ["종합"],
 ["w_face","w 표정·얼굴 상태",0,0.8,0.05],
 ["w_light","w 빛 상태",0,0.8,0.05],
 ["w_image","w 영상 상태",0,0.8,0.05],
 ["w_distort","w 왜곡(판독성) 상태",0,0.8,0.05],
 ["gap_min","픽 간 최소 프레임 gap",0,60,2],
];
const DEF={sym_max:0.6,dev_lo:-15,dev_hi:15,pt_max:99,pu_min:0.4,cs_min:0,mv_min:0,lt_min:0,
           ex_min:0,ex_max:1.0,gap_min:12,dp_min:0,hh_max:100,sp_min:0,pa_min:0,
           w_face:0.45,w_light:0.20,w_image:0.15,w_distort:0.20};
let A={...DEF}, Bcfg=null, GT={}, cur=0, sortMode="time", poseOpen=false, ATT=false;
let selF=null, iMode="포즈", collapsed={};
let _rp=false;   // 렌더 스로틀(rAF) — 풀 전체 표시 + 드래그 부드러움 양립
function scheduleRender(){if(_rp)return;_rp=true;requestAnimationFrame(()=>{_rp=false;render();});}
const STAGES=["포즈","표정·얼굴","빛","영상","왜곡"];
let MUTE={"포즈":false,"표정·얼굴":false,"빛":false,"영상":false,"왜곡":false};   // v0.11 채널 M
const NOMUTE={"포즈":false,"표정·얼굴":false,"빛":false,"영상":false,"왜곡":false};
function anyMute(){return STAGES.some(s=>MUTE[s]);}
function muteG(g){MUTE[g]=!MUTE[g];buildPanel();render();}
function soloG(g){
 const isSolo=!MUTE[g]&&STAGES.every(s=>s==g||MUTE[s]);
 if(isSolo){for(const s of STAGES)MUTE[s]=false;}
 else{for(const s of STAGES)MUTE[s]=(s!=g);}
 buildPanel();render();}
const SCOL=["#c98a4a","#e08aa8","#d8c455","#55aacc","#b070d0"];
const SURV="#69d069";
const K2G={sym_max:"포즈",dev_lo:"포즈",dev_hi:"포즈",pt_max:"포즈",
 pu_min:"표정·얼굴",ex_min:"표정·얼굴",ex_max:"표정·얼굴",
 lt_min:"빛",dp_min:"빛",hh_max:"빛",sp_min:"영상",cs_min:"왜곡",mv_min:"왜곡",
 w_face:"표정·얼굴",w_light:"빛",w_image:"영상",w_distort:"왜곡"};

function gPass(r,c,g){   // 채널별 하드 게이트 (v0.11: mute=게이트 해제)
 if(g==0)return r.sy<c.sym_max&&r.dv>c.dev_lo&&r.dv<c.dev_hi&&Math.abs(r.pc)<c.pt_max;
 if(g==1)return r.pu>=c.pu_min&&r.ex>=c.ex_min&&r.ex<=c.ex_max;
 if(g==2)return (r.lt==null||r.lt>=c.lt_min)&&(r.pa==null||r.pa>=c.pa_min)&&(r.dp==null||r.dp>=c.dp_min)&&(r.hh==null||r.hh<=c.hh_max);
 if(g==3)return r.sp==null||r.sp>=c.sp_min;
 return (r.cs==null||r.cs>=c.cs_min)&&(r.mv==null||r.mv>=c.mv_min);}
function firstFail(r,c,M){
 M=M||MUTE;
 for(let g=0;g<5;g++){if(!M[STAGES[g]]&&!gPass(r,c,g))return g;}
 return -1;}
function pass(r,c,M){return firstFail(r,c,M)<0;}
function funnel(rows,c,M){
 M=M||MUTE;
 const out=[rows.length];
 let cur_=rows;
 for(let g=0;g<5;g++){
  if(!M[STAGES[g]])cur_=cur_.filter(r=>gPass(r,c,g));
  out.push(cur_.length);}
 return out;}
function stateScores(rr){
 return [(2*rr[0]+rr[1])/3, rr[7], (rr[2]+rr[3])/2, (rr[5]+rr[6]+rr[4])/3];}
function score(r,c,lf,M){
 M=M||MUTE;
 const [sf,sl,si,sd]=stateScores(r.r);
 const wl=ATT?c.w_light*(lf==null?1:lf):c.w_light;
 return (M["표정·얼굴"]?0:c.w_face)*sf+(M["빛"]?0:wl)*sl
  +(M["영상"]?0:c.w_image)*si+(M["왜곡"]?0:c.w_distort)*sd;}
function picks(rows,c,lf,M){
 M=M||MUTE;
 const sv=rows.filter(r=>pass(r,c,M));
 sv.forEach(r=>r._s=score(r,c,lf,M));
 sv.sort((a,b)=>b._s-a._s);
 const got=[];
 for(const r of sv){if(got.every(o=>Math.abs(r.f-o.f)>=c.gap_min))got.push(r);if(got.length==3)break;}
 return got.map(r=>r.f);}

function cellHTML(clip,r,cls){
 const k=clip+":"+r.f, fl=GT[k]||"";
 const sel=(selF==r.f)?" selg":"";
 const img=r.th?`<img src="${r.th}" loading="lazy">`:`<div class="noimg">f${r.f}<br>(no thumb)</div>`;
 const cap=`f${r.f} ex${r.ex} pu${r.pu}<br>cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
 const mark=fl=="pos"?"O":fl=="neg"?"X":"";
 return `<div class="cell ${fl} ${cls||""}${sel}" onclick="onCell(event,'${clip}',${r.f})">${img}
   <span class="flag">${mark}</span><div class="cap">${cap}</div></div>`;}

function funnelHTML(fn){
 const names=["전체",...STAGES];
 const cols=["#666",...SCOL.slice(0,STAGES.length-1),SURV];
 const mx=Math.max(fn[0],1), last=fn.length-1;
 return `<div class="funnel">`+fn.map((v,i)=>
  `<div class="fr${i==last?" last":""}"><span class="lbl">${names[i]}</span>
   <span class="bar" style="width:${Math.max(2,Math.round(280*v/mx))}px;background:${cols[i]}"></span>
   <span class="cnt">${v}</span></div>`).join("")+
  (fn[last]<3?`<div class="fr"><span class="lbl"></span><span style="color:#e66">⚠ 풀&lt;3</span></div>`:``)+`</div>`;}

function legendHTML(){
 return `<div class="legend"><span><i style="background:${SURV}"></i>생존</span>`+
  STAGES.map((s,i)=>`<span><i style="background:${SCOL[i]}"></i>${s}에 걸러짐</span>`).join("")+
  `<span><i style="background:rgba(80,170,180,.5)"></i>boarding</span>
   <span><i style="background:#7ac"></i>A 픽</span><span><i style="border:1px dashed #ca7;width:7px;height:7px"></i>B 픽</span>
   <span style="margin-left:8px">유령:</span>
   <span><i style="background:#a05244"></i>무효</span><span><i style="background:#5a78a0"></i>미측정</span>
   <span><i style="background:#8a70b0"></i>파편</span><span><i style="background:#3a3a3a"></i>무검출</span></div>`;}

function render(){
 const sy0=window.scrollY;
 let st_ok=true,st_msg=[],gtP=0,gtN=0,gtPB=0,gtNB=0;
 const isDef=JSON.stringify(A)==JSON.stringify(DEF);
 const meta=WB.clips.map(C=>{
  const pA=picks(C.rows,A,C.lf), fn=funnel(C.rows,A);
  const pB=Bcfg?picks(C.rows,Bcfg,C.lf):null;
  if(isDef&&!ATT&&!anyMute()){const same=JSON.stringify(pA.slice().sort((a,b)=>a-b))==JSON.stringify(C.selftest.slice().sort((a,b)=>a-b));
   if(!same){st_ok=false;st_msg.push(C.clip);}}
  pA.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtP++;if(g=="neg")gtN++;});
  if(pB)pB.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtPB++;if(g=="neg")gtNB++;});
  let p=0,ng=0;for(const k in GT){if(k.startsWith(C.clip+":")){GT[k]=="pos"?p++:ng++;}}
  return {pA,pB,fn,p,ng,alive:fn[fn.length-1]};});

 const tabs=WB.clips.map((C,i)=>
  `<span class="tab${i==cur?" cur":""}" onclick="cur=${i};selF=null;render()">${C.clip}
   <span class="b">${meta[i].alive}</span>${meta[i].p+meta[i].ng?`<span class="g"> +${meta[i].p}/−${meta[i].ng}</span>`:""}</span>`).join("");

 const C=WB.clips[cur], m=meta[cur];
 if(selF==null||!C.rows.some(r=>r.f==selF)) selF=(m.pA[0]!=null?m.pA[0]:(C.rows[0]&&C.rows[0].f));
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 const setA=new Set(m.pA), setB=m.pB?new Set(m.pB):null;
 const gInv=C.ghost.filter(g=>g.k=="inv").length, gDet=C.ghost.filter(g=>g.k=="det").length,
       gFrag=C.ghost.filter(g=>g.k=="frag").length,
       gAbs=C.absent.reduce((a,r)=>a+r[1]-r[0]+1,0);
 let h=`<div id="sticky"><div id="tabs">${tabs}</div><b>${C.clip}</b> t${C.tid} <span class="note">비디오 ${C.vf}f = 측정 ${C.n}`+
  (gInv?` + 무효 ${gInv}`:"")+(gDet?` + 미측정 ${gDet}`:"")+(gFrag?` + 파편 ${gFrag}`:"")+(gAbs?` + 무검출 ${gAbs}`:"")+
  ` · <b>빛 판별력 lf=${C.lf==null?"?":C.lf}</b>${ATT?` <span style="color:#fc6">(감쇠: w_light ${A.w_light}→${(A.w_light*(C.lf==null?1:C.lf)).toFixed(2)})</span>`:""}`+
  (anyMute()?` · <span style="color:#e06666"><b>${STAGES.filter(s=>!MUTE[s]).length==1?"SOLO: "+STAGES.find(s=>!MUTE[s]):"MUTE: "+STAGES.filter(s=>MUTE[s]).join(", ")}</b></span>`:"")+
  ` · 풀 정렬:</span>
  <button onclick="sortMode=sortMode=='time'?'score':'time';render()">${sortMode=='time'?'시간순':'점수순'}</button>
  <button onclick="poseOpen=!poseOpen;render()">포즈 눈금 ${poseOpen?'닫기':'보기'}</button>
  <label style="font-size:12px;color:#bbb;margin-left:6px"><input type="checkbox" ${ATT?"checked":""}
   onchange="ATT=this.checked;render()"> 빛 분산-감쇠(시험)</label>`;
 h+=`<div id="tl"><canvas id="tlc" width="1000" height="44"></canvas><div id="tlTip"></div></div>`+legendHTML()+`</div>`;
 h+=`<div class="box"><div class="boxttl">결과 — 퍼널·픽</div>`+funnelHTML(m.fn);
 if(poseOpen){
  const wt=C.rows.filter(r=>r.th);
  const samp=a=>{if(a.length<=8)return a;const o=[];for(let i=0;i<8;i++)o.push(a[Math.round(i*(a.length-1)/7)]);return [...new Set(o)];};
  const byDev=samp(wt.slice().sort((a,b)=>a.dv-b.dv));
  const bySy=samp(wt.slice().sort((a,b)=>a.sy-b.sy));
  const pose=r=>{const ff=firstFail(r,A);const dim=(ff===0||ff===1)?"opacity:.35":"";
   return `<div class="cell" style="${dim}" onclick="groundPose('${C.clip}',${r.f})"><img src="${r.th}" loading="lazy">
    <div class="cap">dv${r.dv} sy${r.sy}<br>pt${r.pt==null?"--":r.pt} pc${r.pc}</div></div>`;};
  h+=`<div class="rowlbl">포즈 눈금 — yaw 사다리 (좌→정면→우 · 클릭=밴드 확장 그라운딩 · 흐림=포즈 스크린에 걸러짐)</div>
   <div class="strip sm">`+byDev.map(pose).join("")+`</div>
   <div class="rowlbl">포즈 눈금 — sym 사다리</div><div class="strip sm">`+bySy.map(pose).join("")+`</div>`;
 }
 h+=`<div class="rowlbl">CURRENT (생산 likeness.json)</div><div class="strip sm">`+
   C.cur.map(f=>byf[f]?cellHTML(C.clip,byf[f],""):"").join("")+`</div>`;
 h+=`<div class="rowlbl">A 픽</div><div class="strip big">`+
   m.pA.map(f=>cellHTML(C.clip,byf[f],"pickA"+(setB&&!setB.has(f)?" diff":""))).join("")+`</div>`;
 if(m.pB)h+=`<div class="rowlbl">B 픽</div><div class="strip big">`+
   m.pB.map(f=>cellHTML(C.clip,byf[f],"pickB"+(!setA.has(f)?" diff":""))).join("")+`</div>`;
 if(anyMute()){   // v0.11 diff 뷰: solo/뮤트 선택 vs 종합(뮤트 해제) 선택 — 1층→2층 다리
  const pRef=picks(C.rows,A,C.lf,NOMUTE);
  h+=`<div class="rowlbl">믹스 픽 (뮤트 해제 기준 — 주황 외곽=현재 solo/뮤트 픽과 불일치)</div><div class="strip big">`+
   pRef.map(f=>byf[f]?cellHTML(C.clip,byf[f],(setA.has(f)?"":"diff ")+"pickB"):"").join("")+`</div>`;
 }
 h+=`</div>`;   // 결과 박스 닫기
 const sv=C.rows.filter(r=>pass(r,A));
 sv.forEach(r=>r._s=score(r,A,C.lf));
 const ordered=sortMode=="time"?sv.slice().sort((a,b)=>a.f-b.f):sv.slice().sort((a,b)=>b._s-a._s);
 h+=`<div class="box"><div class="boxttl">생존 풀 (A, ${sv.length}행 전체 · ${sortMode=='time'?'시간순':'점수순'})</div>
  <div class="strip sm">`+ordered.map(r=>cellHTML(C.clip,r,"")).join("")+`</div></div>`;
 document.getElementById("main").innerHTML=h;
 drawTimeline(C,m);
 drawDialHists(C,m);
 renderInsp(C,m);

 const st=document.getElementById("selftest");
 if(isDef&&!ATT&&!anyMute()){st.textContent=st_ok?"selftest OK — JS ≡ python (기본 설정)":"selftest FAIL: "+st_msg.join(",");
  st.className=st_ok?"ok":"bad";}
 else{st.textContent="탐색 중 (기본값 아님/뮤트 중 — selftest는 기본값·전 채널에서만)";st.className="";}
 const tot=Object.keys(GT).length;
 document.getElementById("gtscore").textContent=
  tot?`GT ${tot}개 · A: +${gtP}/−${gtN}`+(Bcfg?` · B: +${gtPB}/−${gtNB}`:""):"";
 const ms=document.getElementById("mstat");
 if(ms)ms.innerHTML=`생존 ${m.fn[m.fn.length-1]}행 → 픽 ${m.pA.length}장`+(Bcfg?`<br>B 프리셋 활성`:``)+(anyMute()?`<br><span style="color:#e06666">뮤트 중</span>`:``);
 for(const d of DIALS){if(d.length==1)continue;const k=d[0];
  const el=document.getElementById("d_"+k);
  if(el)el.className="dial"+(A[k]!=DEF[k]?" mod":"")+((K2G[k]&&MUTE[K2G[k]])?" gmute":"");}
 window.scrollTo(0,sy0);
}

const HSPEC={
 sym_max:{f:r=>r.sy,dir:"below"},
 dev_hi:{f:r=>r.dv,band:["dev_lo","dev_hi"]},
 pt_max:{f:r=>Math.abs(r.pc),dir:"below"},
 pu_min:{f:r=>r.pu,dir:"above"},
 cs_min:{f:r=>r.cs,dir:"above"},
 mv_min:{f:r=>r.mv,dir:"above"},
 lt_min:{f:r=>r.lt,dir:"above"},
 pa_min:{f:r=>r.pa,dir:"above"},
 dp_min:{f:r=>r.dp,dir:"above"},
 hh_max:{f:r=>r.hh,dir:"below"},
 sp_min:{f:r=>r.sp,dir:"above"},
 ex_max:{f:r=>r.ex,band:["ex_min","ex_max"]},
};
function drawDialHists(C,m){
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 for(const d of DIALS){
  if(d.length==1)continue;
  const [k,,mn,mx]=d, sp=HSPEC[k];
  if(!sp)continue;
  const cv=document.getElementById("h_"+k);
  if(!cv)continue;
  const ctx=cv.getContext("2d"), W=cv.width, H=cv.height;
  ctx.clearRect(0,0,W,H);
  const vals=[];
  for(const r of C.rows){const v=sp.f(r);if(v!=null&&isFinite(v))vals.push(v);}
  const NB=40, bins=new Array(NB).fill(0);
  for(const v of vals){let b=Math.floor((Math.min(mx,Math.max(mn,v))-mn)/(mx-mn)*NB);
   if(b>=NB)b=NB-1;if(b<0)b=0;bins[b]++;}
  const bm=Math.max(...bins,1), thr=A[k];
  const isBand=!!sp.band, blo=isBand?A[sp.band[0]]:null, bhi=isBand?A[sp.band[1]]:null;
  const tx=v=>4+(Math.min(mx,Math.max(mn,v))-mn)/(mx-mn)*(W-8);
  const inPass=v=>isBand?(v>blo&&v<bhi):(sp.dir=="below"?v<thr:v>=thr);
  for(let i=0;i<NB;i++){
   const x0=4+i*(W-8)/NB, bh=Math.round((H-13)*bins[i]/bm);
   const mid=mn+(i+0.5)*(mx-mn)/NB;
   ctx.fillStyle=inPass(mid)?"#6f9b6f":"#484848";
   ctx.fillRect(x0,H-3-bh,Math.max(1,(W-8)/NB-1),bh);
  }
  ctx.fillStyle="#fc6";
  if(isBand){ctx.fillRect(tx(blo)-0.8,1,1.6,H-2);ctx.fillRect(tx(bhi)-0.8,1,1.6,H-2);}
  else ctx.fillRect(tx(thr)-0.8,1,1.6,H-2);
  ctx.fillStyle="#7ac";
  for(const f of m.pA){const r=byf[f];if(!r)continue;const v=sp.f(r);if(v==null||!isFinite(v))continue;
   const x=tx(v);ctx.beginPath();ctx.moveTo(x,H-2);ctx.lineTo(x-3,H-9);ctx.lineTo(x+3,H-9);ctx.closePath();ctx.fill();}
  let np=0;
  for(const v of vals){if(inPass(v))np++;}
  ctx.fillStyle="#bbb";ctx.font="9px sans-serif";ctx.textAlign="right";
  ctx.fillText(Math.round(100*np/Math.max(vals.length,1))+"%",W-3,9);
  ctx.textAlign="left";
 }
}

function drawTimeline(C,m){
 const cv=document.getElementById("tlc");
 if(!cv)return;
 const ctx=cv.getContext("2d"), W=cv.width, H=cv.height;
 ctx.clearRect(0,0,W,H);
 const fmin=0, fmax=Math.max(C.vf-1, 1);
 const X=f=>4+(f-fmin)/(fmax-fmin)*(W-8);
 ctx.fillStyle="rgba(80,170,180,0.22)";
 for(const r of C.rows) if(r.b) ctx.fillRect(X(r.f)-1,0,2.2,H-8);
 for(const r of C.rows){
  const ff=firstFail(r,A);
  ctx.fillStyle=ff<0?SURV:SCOL[ff];
  if(ff<0) ctx.fillRect(X(r.f),12,1.7,H-20);
  else     ctx.fillRect(X(r.f),20,1.4,H-28);
 }
 ctx.fillStyle="#3a3a3a";
 for(const ab of C.absent) ctx.fillRect(X(ab[0]),H-7,Math.max(1.5,X(ab[1])-X(ab[0])+1.5),6);
 const GCOL={inv:"#a05244",det:"#5a78a0",frag:"#8a70b0"};
 for(const g of C.ghost){ctx.fillStyle=GCOL[g.k];ctx.fillRect(X(g.f),H-7,1.6,6);}
 ctx.fillStyle="#7ac";
 for(const f of m.pA) ctx.fillRect(X(f)-1.5,9,3,H-17);
 if(m.pB){ctx.strokeStyle="#ca7";ctx.setLineDash([3,2]);
  for(const f of m.pB) ctx.strokeRect(X(f)-2.5,9,5,H-18);
  ctx.setLineDash([]);}
 if(selF!=null){ctx.strokeStyle="#f90";ctx.strokeRect(X(selF)-2.5,1,5,H-2);}
 for(const r of C.rows){
  const g=GT[C.clip+":"+r.f];
  if(!g)continue;
  ctx.fillStyle=g=="pos"?"#4e4":"#e44";
  ctx.beginPath();ctx.arc(X(r.f),4.5,2.6,0,7);ctx.fill();
 }
 const tip=document.getElementById("tlTip");
 const GLBL={inv:"게이트-무효 (측정됨, valid 밖)",det:"미측정 — 검출만 (랜드마크 없음)",
             frag:"트랙 파편 (동일 인물 추정)"};
 const uni=C.rows.map(r=>({f:r.f,row:r})).concat(C.ghost.map(g=>({f:g.f,g:g})))
   .sort((a,b)=>a.f-b.f);
 const nearest=x=>{const fe=fmin+(x-4)/(W-8)*(fmax-fmin);
  let bi=0,bd=1e9;
  for(let i=0;i<uni.length;i++){const d=Math.abs(uni[i].f-fe);if(d<bd){bd=d;bi=i;}}
  return uni[bi];};
 cv.onmousemove=e=>{
  const rect=cv.getBoundingClientRect(), x=e.clientX-rect.left;
  const o=nearest(x);
  const gflag=GT[C.clip+":"+o.f], gs=gflag?` · GT:${gflag=="pos"?"＋":"−"}`:"";
  if(o.row){
   const r=o.row, ff=firstFail(r,A);
   const st=ff<0?`<span style="color:${SURV}">생존</span>`:`<span style="color:${SCOL[ff]}">${STAGES[ff]}에 걸러짐</span>`;
   const ss=stateScores(r.r);
   tip.innerHTML=(r.th?`<img src="${r.th}" loading="lazy">`:"")+
    `f${r.f} ${st}${gs}<br>ex${r.ex} pu${r.pu} sy${r.sy} dv${r.dv}<br>상태: 얼굴${ss[0].toFixed(2)} 빛${ss[1].toFixed(2)} 영상${ss[2].toFixed(2)} 왜곡${ss[3].toFixed(2)}`;
  }else{
   const g=o.g;
   tip.innerHTML=(g.th?`<img src="${g.th}" loading="lazy">`:"")+
    `f${g.f} <span style="color:${GCOL[g.k]}">${GLBL[g.k]}</span>${gs}<br>측정 신호 없음`;
  }
  tip.style.display="block";
  tip.style.left=Math.min(x+14,W-140)+"px";
  tip.style.top="46px";
 };
 cv.onmouseleave=()=>{tip.style.display="none";};
 cv.onclick=e=>{
  const rect=cv.getBoundingClientRect();
  const o=nearest(e.clientX-rect.left);
  if(e.shiftKey&&o.row){groundPose(C.clip,o.f);return;}
  selF=o.f;render();
 };
}

// ── 검사 패널(v0.10): 활성 상태의 분석 시각화 ─────────────────────────
function drawMask(r){   // v0.17: skin 마스크 재현 — hull 클립 + 20앵커 가우시안(σ=0.16 IOD)
 const cv=document.getElementById("mkc");
 if(!cv||!r.sk||!r.th)return;
 const ctx=cv.getContext("2d"), img=new Image();
 img.onload=()=>{
  ctx.drawImage(img,0,0,224,224);
  const o=r.sk.o.map(p=>[p[0]*224,p[1]*224]);
  const path=()=>{ctx.beginPath();ctx.moveTo(o[0][0],o[0][1]);
   for(const p of o.slice(1))ctx.lineTo(p[0],p[1]);ctx.closePath();};
  const iod=Math.hypot((r.sk.e[0][0]-r.sk.e[1][0])*224,(r.sk.e[0][1]-r.sk.e[1][1])*224);
  const sig=Math.max(0.16*iod,2);
  ctx.save();path();ctx.clip();
  ctx.globalCompositeOperation="lighter";
  for(const a of r.sk.a){
   const g=ctx.createRadialGradient(a[0]*224,a[1]*224,0,a[0]*224,a[1]*224,2.5*sig);
   g.addColorStop(0,"rgba(60,255,120,0.30)");g.addColorStop(1,"rgba(60,255,120,0)");
   ctx.fillStyle=g;ctx.fillRect(0,0,224,224);}
  ctx.restore();
  ctx.strokeStyle="rgba(120,220,140,0.85)";ctx.lineWidth=1;path();ctx.stroke();
  // v0.18 패턴 영역 마커: 볼=청록 · 턱 후방=주황 (영역 인덱스 자가 검증)
  if(r.sk.c)for(const p of r.sk.c){ctx.strokeStyle="rgba(70,220,220,0.95)";ctx.lineWidth=1.5;
   ctx.beginPath();ctx.arc(p[0]*224,p[1]*224,0.8*sig,0,7);ctx.stroke();}
  if(r.sk.j)for(const p of r.sk.j){ctx.strokeStyle="rgba(255,150,30,0.95)";ctx.lineWidth=1.5;
   ctx.beginPath();ctx.arc(p[0]*224,p[1]*224,0.6*sig,0,7);ctx.stroke();}
 };
 img.src=r.th;}
function drawLmap(r){   // v0.17: 32×32 광량 맵 재현(bbox 크롭→그레이→5탭 블러) + lr/tb 재계산 대조
 const cv=document.getElementById("dmc");
 if(!cv||!r.th)return;
 const ctx=cv.getContext("2d"), img=new Image();
 img.onload=()=>{
  const bb=r.bb||[0,0,1,1];
  const t=document.createElement("canvas");t.width=32;t.height=32;
  const tc=t.getContext("2d");
  tc.drawImage(img,bb[0]*224,bb[1]*224,Math.max((bb[2]-bb[0])*224,1),Math.max((bb[3]-bb[1])*224,1),0,0,32,32);
  const id=tc.getImageData(0,0,32,32), d=id.data;
  let g=new Float32Array(1024);
  for(let i=0;i<1024;i++)g[i]=0.299*d[i*4]+0.587*d[i*4+1]+0.114*d[i*4+2];
  const K=[1,4,6,4,1];
  const blur=(src,horiz)=>{const out=new Float32Array(1024);
   for(let y=0;y<32;y++)for(let x=0;x<32;x++){let s=0,w=0;
    for(let k=-2;k<=2;k++){const xx=horiz?x+k:x, yy=horiz?y:y+k;
     if(xx<0||xx>31||yy<0||yy>31)continue;
     s+=K[k+2]*src[yy*32+xx];w+=K[k+2];}
    out[y*32+x]=s/w;}
   return out;};
  g=blur(blur(g,true),false);
  let L=0,R=0,T=0,B=0;
  for(let y=0;y<32;y++)for(let x=0;x<32;x++){const v=g[y*32+x];
   if(x<16)L+=v;else R+=v;if(y<16)T+=v;else B+=v;}
  const lr=((L-R)/(L+R+1e-6)).toFixed(3), tb=((T-B)/(T+B+1e-6)).toFixed(3);
  for(let i=0;i<1024;i++){const v=Math.round(g[i]);
   d[i*4]=v;d[i*4+1]=v;d[i*4+2]=v;d[i*4+3]=255;}
  tc.putImageData(id,0,0);
  ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,128,128);
  ctx.drawImage(t,0,0,128,128);
  ctx.strokeStyle="rgba(216,196,85,0.5)";
  ctx.beginPath();ctx.moveTo(64,0);ctx.lineTo(64,128);ctx.moveTo(0,64);ctx.lineTo(128,64);ctx.stroke();
  const lv=document.getElementById("lmv");
  if(lv)lv.textContent=`재현 lr ${lr} tb ${tb} (저장 ${r.lr??"--"} / ${r.tb??"--"})`;
 };
 img.src=r.th;}
function shEval(sh,x,y,z){
 return sh[0]*0.2821+sh[1]*0.4886*y+sh[2]*0.4886*z+sh[3]*0.4886*x
  +sh[4]*1.0925*x*y+sh[5]*1.0925*y*z+sh[6]*0.3154*(3*z*z-1)
  +sh[7]*1.0925*x*z+sh[8]*0.5462*(x*x-y*y);}
function renderInsp(C,m){
 const el=document.getElementById("insp");
 const r=C.rows.find(r=>r.f==selF);
 if(!r){el.innerHTML=`<div class="note">프레임을 클릭해 선택하세요.</div>`;return;}
 const ss=stateScores(r.r), pv=(C.pv||{})[String(r.f)];
 const gflag=GT[C.clip+":"+r.f]||"";
 const tabs=STAGES.map(s=>`<span class="itab${s==iMode?" cur":""}" onclick="iMode='${s}';render()">${s}</span>`).join("");
 let body="";
 if(iMode=="포즈"){
  body=`<canvas id="ovl" width="300" height="300" style="border:1px solid #444"></canvas>
   <div class="note">yaw dev ${r.dv}° · pitch ${r.pt==null?"--":r.pt}°(Δ${r.pc}) · roll ${r.rl==null?"--":r.rl}° · sym ${r.sy}</div>
   <div class="note">${pv?"랜드마크 오버레이 = 추정 검증":"오버레이는 픽 프레임 한정 (콘솔 온디맨드 확장 예정)"}</div>`;
 }else if(iMode=="표정·얼굴"){
  body=pv?`<div>${pv.bs.map(([nm,v])=>`<div class="ibar"><span class="nm">${nm}</span>
    <span class="bv" style="width:${Math.round(v*150)}px"></span> ${v}</div>`).join("")}</div>
    <div class="note">pupil ${r.pu} · ex(비 eyeLook 최대) ${r.ex}</div>`
   :`<div class="note">blendshape 상세는 픽 프레임 한정. pupil ${r.pu} · ex ${r.ex}</div>`;
 }else if(iMode=="빛"){
  body=`<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start">
    <div><canvas id="mkc" width="224" height="224" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">skin 마스크 (초록=가중, 선=타원 hull)</div></div>
    <div><canvas id="dmc" width="128" height="128" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">32×32 광량 맵 (bbox)<br><span id="lmv" style="color:#d8c455"></span></div></div>
   </div>
   <div style="display:flex;gap:10px;align-items:flex-start;margin-top:8px">
    <div><canvas id="shc" width="96" height="96" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">SH 조명 구면</div></div>
    <div><canvas id="lrc" width="96" height="96" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">lr/tb 방향</div></div></div>
   <div class="note"><b>lt ${r.lt==null?"--":r.lt}% = (휘도 ${r.lm==null?"--":r.lm}% + 색량 ${r.ch==null?"--":r.ch}%)/2</b><br>
    <b>패턴 pa ${r.pa==null?"--":r.pa}%</b> (볼빛−턱그늘 raw ${r.par==null?"--":r.par}) · 입체감 dp ${r.dp==null?"--":r.dp}% · 거칠기 hh ${r.hh==null?"--":r.hh}%<br>
    lr ${r.lr==null?"--":r.lr} · tb ${r.tb==null?"--":r.tb} · 클립 판별력 lf=${C.lf}<br>
    <span style="color:#4dd">마스크 위 청록=볼 삼각형</span> · <span style="color:#f90">주황=턱 후방 경계</span></div>`;
 }else if(iMode=="영상"){
  body=(pv&&pv.lap)?`<img src="thumbs/${C.clip}/f${String(r.f).padStart(5,"0")}_lap.jpg" style="width:224px;border:1px solid #444">
    <div class="note">Laplacian 선명 히트맵 (밝음=엣지 살아있음)</div>
    <div class="note">선명 sp ${r.sp==null?"--":r.sp}%</div>`
   :`<div class="note">선명 히트맵은 픽 프레임 한정. sp ${r.sp==null?"--":r.sp}%</div>`;
 }else{ // 왜곡
  body=`<canvas id="csc" width="300" height="80" style="border:1px solid #444"></canvas>
   <div class="note">실선=cs(정체성 판독성 pct) · 점선=mv(입-가시 pct) · 주황=선택 프레임</div>
   <div class="note">cs ${r.cs==null?"--":r.cs}% · mv ${r.mv==null?"--":r.mv}% · norm rank ${(r.r[4]*100).toFixed(0)}%</div>`;
 }
 el.innerHTML=`<div class="rowlbl">검사 — f${r.f} ${r.b?"(boarding)":""}</div>
  <img id="inspImg" src="${r.th||""}" ${r.th?"":'style="opacity:.2"'}>
  <div class="note" style="margin:4px 0">상태점수: 얼굴 <b>${ss[0].toFixed(2)}</b> · 빛 <b>${ss[1].toFixed(2)}</b> · 영상 <b>${ss[2].toFixed(2)}</b> · 왜곡 <b>${ss[3].toFixed(2)}</b></div>
  <div class="gtbtn">GT: <button onclick="setGT('pos')" ${gflag=="pos"?'style="border-color:#5c5;color:#5c5"':''}>＋ 긍정</button>
   <button onclick="setGT('neg')" ${gflag=="neg"?'style="border-color:#e55;color:#e55"':''}>− 부정</button>
   <button onclick="setGT(null)">지움</button></div>
  <div class="itabs">${tabs}</div>${body}`;
 if(iMode=="포즈"){
  const cv=document.getElementById("ovl"), ctx=cv.getContext("2d");
  const img=new Image();
  img.onload=()=>{ctx.drawImage(img,0,0,300,300);
   if(pv){ctx.strokeStyle="rgba(80,255,120,0.8)";ctx.lineWidth=1;
    for(const [a,b] of WB.edges){const p=pv.lm[a],q=pv.lm[b];
     ctx.beginPath();ctx.moveTo(p[0]*300,p[1]*300);ctx.lineTo(q[0]*300,q[1]*300);ctx.stroke();}}};
  if(r.th)img.src=r.th;
 }else if(iMode=="빛"){
  drawMask(r);
  drawLmap(r);
 }
 if(iMode=="빛"&&r.sh){
  const cv=document.getElementById("shc"), ctx=cv.getContext("2d");
  const im=ctx.createImageData(96,96);
  let lo=1e9,hi=-1e9;const vals=new Float32Array(96*96).fill(NaN);
  for(let py=0;py<96;py++)for(let px=0;px<96;px++){
   const x=(px-48)/46,y=(py-48)/46,r2=x*x+y*y;
   if(r2>1)continue;
   const z=Math.sqrt(1-r2);
   const v=shEval(r.sh,x,-y,z);
   vals[py*96+px]=v;if(v<lo)lo=v;if(v>hi)hi=v;}
  for(let i=0;i<96*96;i++){const v=vals[i];
   const g=isNaN(v)?22:Math.round((v-lo)/(hi-lo+1e-9)*235+20);
   im.data[i*4]=g;im.data[i*4+1]=g;im.data[i*4+2]=g;im.data[i*4+3]=255;}
  ctx.putImageData(im,0,0);
  const lc=document.getElementById("lrc"), c2=lc.getContext("2d");
  c2.fillStyle="#222";c2.fillRect(0,0,96,96);
  c2.strokeStyle="#555";c2.strokeRect(20,20,56,56);
  if(r.lr!=null&&r.tb!=null){
   c2.strokeStyle="#d8c455";c2.lineWidth=2;c2.beginPath();c2.moveTo(48,48);
   c2.lineTo(48+r.lr*40,48-r.tb*40);c2.stroke();
   c2.fillStyle="#d8c455";c2.beginPath();c2.arc(48+r.lr*40,48-r.tb*40,3,0,7);c2.fill();}
 }
 if(iMode=="왜곡"){
  const cv=document.getElementById("csc"), ctx=cv.getContext("2d");
  ctx.fillStyle="#141414";ctx.fillRect(0,0,300,80);
  const X=f=>4+f/Math.max(C.vf-1,1)*292;
  const plot=(get,style,dash)=>{ctx.strokeStyle=style;ctx.setLineDash(dash||[]);
   ctx.beginPath();let started=false;
   for(const q of C.rows){const v=get(q);if(v==null)continue;
    const x=X(q.f),y=76-v/100*72;
    if(!started){ctx.moveTo(x,y);started=true;}else ctx.lineTo(x,y);}
   ctx.stroke();ctx.setLineDash([]);};
  plot(q=>q.cs,"#b070d0");
  plot(q=>q.mv,"#55aacc",[3,2]);
  ctx.strokeStyle="#f90";ctx.beginPath();ctx.moveTo(X(r.f),2);ctx.lineTo(X(r.f),78);ctx.stroke();
 }
 // v0.13 미터 브리지: 선택 프레임의 상태점수 실시간 (탭 바 우측, 전 채널 상시)
 const mm={"표정·얼굴":ss[0],"빛":ss[1],"영상":ss[2],"왜곡":ss[3]};
 for(const g in mm){const el2=document.getElementById("mt_"+g);
  if(el2)el2.style.width=Math.round(mm[g]*100)+"%";}
 const mp=document.getElementById("mt_포즈");
 if(mp)mp.textContent=`포즈 dv${r.dv} sy${r.sy}`;
}
function onCell(e,clip,f){
 if(e&&e.shiftKey){groundPose(clip,f);return;}
 selF=f;render();}
function setGT(v){
 const C=WB.clips[cur];
 const k=C.clip+":"+selF;
 if(v)GT[k]=v;else delete GT[k];
 render();}
function groundPose(clip,f){
 const C=WB.clips.find(c=>c.clip==clip);
 const r=C&&C.rows.find(r=>r.f==f);
 if(!r)return;
 A.sym_max=Math.min(2.0,Math.round((Math.floor(r.sy/0.05)+1)*5)/100);
 A.dev_lo=Math.min(A.dev_lo,Math.max(-90,Math.floor(r.dv)-1));
 A.dev_hi=Math.max(A.dev_hi,Math.min(90,Math.floor(r.dv)+1));
 if(A.pt_max<99)A.pt_max=Math.max(A.pt_max,Math.min(99,Math.floor(Math.abs(r.pc))+1));
 buildPanel();render();}
function snapshotB(){Bcfg={...A};render();}
function clearB(){Bcfg=null;render();}
function resetA(){A={...DEF};buildPanel();render();}
function exportGT(){
 const lines=Object.entries(GT).map(([k,v])=>{const i=k.indexOf(":");
  return JSON.stringify({schema:"momentscan.workbench-gt/v0",clip:k.slice(0,i),frame:+k.slice(i+1),
    role:"center",flag:v,corpus:"output/l2",ts:new Date().toISOString()});});
 const blob=new Blob([lines.join("\\n")+"\\n"],{type:"application/jsonl"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);
 a.download="workbench_gt.jsonl";a.click();}
function importGT(inp){const fr=new FileReader();fr.onload=()=>{
 fr.result.split("\\n").filter(x=>x.trim()).forEach(l=>{try{const o=JSON.parse(l);
  if(o.flag)GT[o.clip+":"+o.frame]=o.flag;}catch(e){}});render();};
 fr.readAsText(inp.files[0]);}
const D2META={};for(const d of DIALS){if(d.length>1)D2META[d[0]]=d;}
const STRIPS=[   // v0.14: 채널 → 세부 채널(트리) → 다이얼
 {g:"포즈",fader:null,subs:[
   {t:"보이는-정면 (뺨 대칭)",dials:["sym_max"]},
   {t:"yaw 밴드 (좌− / 우+)",dials:["dev_lo","dev_hi"]},
   {t:"pitch (클립상대)",dials:["pt_max"]}]},
 {g:"표정·얼굴",fader:"w_face",subs:[
   {t:"눈동자 가시",dials:["pu_min"]},
   {t:"표정 밴드",dials:["ex_min","ex_max"]}]},
 {g:"빛",fader:"w_light",subs:[
   {t:"조도·생동 (lum×chroma)",dials:["lt_min"]},
   {t:"패턴 (볼빛−턱그늘)",dials:["pa_min"]},
   {t:"입체감 (방향성)",dials:["dp_min"]},
   {t:"거칠기 (harsh)",dials:["hh_max"]}]},
 {g:"영상",fader:"w_image",subs:[
   {t:"선명 (face blur)",dials:["sp_min"]}]},
 {g:"왜곡",fader:"w_distort",subs:[
   {t:"정체성 판독성 (cos_self)",dials:["cs_min"]},
   {t:"입-가시 (가림)",dials:["mv_min"]}]},
];
const MCOL={"표정·얼굴":"#e08aa8","빛":"#d8c455","영상":"#55aacc","왜곡":"#b070d0"};
let deckTab="포즈";
function setTab(g){deckTab=g;if(STAGES.includes(g))iMode=g;buildPanel();render();}
function dialHTML(k){
 const [,lbl,mn,mx,stp]=D2META[k];
 return `<div class="dial" id="d_${k}"><label>${lbl}<span id="v_${k}">${A[k]}</span></label>
  <input type="range" min="${mn}" max="${mx}" step="${stp}" value="${A[k]}"
   oninput="A['${k}']=+this.value;document.getElementById('v_${k}').textContent=this.value;
    if(K2G['${k}']&&STAGES.includes(K2G['${k}']))iMode=K2G['${k}'];scheduleRender()">`+
  (HSPEC[k]?`<canvas class="dh" id="h_${k}" width="300" height="34" style="width:100%"></canvas>`:``)+`</div>`;}
function buildPanel(){   // v0.13: 채널 탭 데크 + 미터 브리지
 const p=document.getElementById("deck");
 let tabs=STRIPS.map(S=>{
  const g=S.g;
  const isSolo=!MUTE[g]&&STAGES.every(s=>s==g||MUTE[s]);
  return `<span class="dtab${deckTab==g?" cur":""}${MUTE[g]?" dm":""}" onclick="setTab('${g}')">${g}
   <span class="sm s${isSolo?" on":""}" onclick="event.stopPropagation();soloG('${g}')">S</span>
   <span class="sm m${MUTE[g]?" on":""}" onclick="event.stopPropagation();muteG('${g}')">M</span></span>`;
 }).join("")+`<span class="dtab${deckTab=="마스터"?" cur":""}" onclick="setTab('마스터')" style="color:#cb8">마스터</span>`;
 const bridge=`<div id="bridge">`+STAGES.slice(1).map(g=>
  `<span class="bm">${g}<span class="bar"><i id="mt_${g}" style="width:0;background:${MCOL[g]}"></i></span></span>`).join("")+
  `<span class="bm" id="mt_포즈" style="color:#c98a4a"></span></div>`;
 let body="";
 if(deckTab=="마스터"){
  body=`<div class="chanview"><div class="body">`+dialHTML("gap_min")+
   `<label style="font-size:12px;color:#bbb;display:block;margin:8px 0"><input type="checkbox" ${ATT?"checked":""}
     onchange="ATT=this.checked;render()"> 빛 분산-감쇠(lf)</label></div>
   <div class="fblock"><div class="note"><span id="mstat"></span><br><br>
    <b>S</b>=솔로(1층 검증) · <b>M</b>=뮤트(게이트 해제+가중 0)<br>
    다이얼 터치 → 우측 검사 뷰 전환 · 주황 •=기본값 이탈</div></div></div>`;
 }else{
  const S=STRIPS.find(s=>s.g==deckTab);
  body=`<div class="chanview${MUTE[S.g]?" gmuted":""}"><div class="body">`+
   S.subs.map(sub=>`<div class="subch"><div class="subttl">${sub.t}</div>`+
    sub.dials.map(dialHTML).join("")+`</div>`).join("")+`</div><div class="fblock">`+
   (S.fader?`<div class="fader"><span class="mlbl">가중 페이더</span>
     <input type="range" min="0" max="0.8" step="0.05" value="${A[S.fader]}"
      oninput="A['${S.fader}']=+this.value;document.getElementById('fv_${S.fader}').textContent=this.value;iMode='${S.g}';scheduleRender()">
     <span class="fv" id="fv_${S.fader}">${A[S.fader]}</span></div>`
    :`<div class="note" style="font-size:11px">밴드=쿼리 (점수 없음)</div>`)+
   `</div></div>`;
 }
 p.innerHTML=`<div id="dtabs">${tabs}</div>${bridge}${body}`;}
document.addEventListener("keydown",e=>{
 if(e.target.tagName=="INPUT")return;
 if(e.key=="ArrowRight"){cur=(cur+1)%WB.clips.length;selF=null;render();}
 if(e.key=="ArrowLeft"){cur=(cur+WB.clips.length-1)%WB.clips.length;selF=null;render();}});
buildPanel();render();
</script></body></html>
"""

if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workbench_out")
    wb = dst
    wb.mkdir(parents=True, exist_ok=True)
    clips = []
    for clip in CLIPS:
        try:
            clips.append(build_clip(clip, out_root, wb))
            print(f"{clip}: rows={clips[-1]['n']} selftest={clips[-1]['selftest']}")
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    (wb / "data.js").write_text(
        "const WB=" + json.dumps({"clips": clips, "edges": EDGES}, ensure_ascii=False) + ";",
        encoding="utf-8")
    (wb / "workbench.html").write_text(HTML, encoding="utf-8")
    print("workbench:", wb / "workbench.html")
