"""Report — the RESULT-consumer surface: one self-contained index.html per clip.

The adoption story's front door (a teammate who never learns the pipeline):
`momentscan run <clip>` ends with one file to open — deliverables first
(portraits · highlight clips · likeness summary), the inspector linked for
anyone who asks WHY. Pure reader over the stash (relative links to artifacts
already in the clip dir; no recomputation, no copies).
"""
from __future__ import annotations

import html
import json
import logging
import time
from pathlib import Path

from momentscan.stash import clip_dir

log = logging.getLogger("momentscan.surface.report")

_CSS = """
body{background:#101014;color:#ddd;font-family:'Noto Sans CJK KR',system-ui,sans-serif;margin:0;padding:24px 32px;}
h1{font-size:20px;margin:0 0 4px}h2{font-size:14px;color:#9a9aa5;margin:26px 0 10px;border-bottom:1px solid #26262e;padding-bottom:4px}
.meta{color:#666;font-size:12px}.grid{display:flex;flex-wrap:wrap;gap:14px}
.card{background:#17171d;border:1px solid #26262e;border-radius:8px;padding:10px;max-width:230px}
.card img{width:100%;border-radius:4px;display:block}.card video{width:320px;border-radius:4px;display:block}
.card .cap{font-size:11.5px;color:#9a9aa5;margin-top:6px;line-height:1.5}
.kv{font-size:12.5px;line-height:1.9}.kv b{color:#7ab0ea}
.chip{display:inline-block;background:#22242c;border-radius:4px;padding:1px 7px;font-size:11px;margin-right:5px}
a{color:#7ab0ea;text-decoration:none}a:hover{text-decoration:underline}
.warn{color:#d68a2e;font-size:12px}
"""


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def render_report(out_root, clip_id: str) -> dict:
    """Assemble <clip>/index.html from persisted deliverables. Tolerant: missing
    stages render as an honest '없음' line, never a crash."""
    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    pj = _load(cdir / "portraits" / "portrait.json") or {}
    lk = _load(cdir / "likeness.json") or {}
    prov = _load(cdir / "provenance.json") or {}
    hls = sorted((cdir / "highlights").glob("*.mp4")) if (cdir / "highlights").is_dir() else []
    inspect_html = cdir / "inspect" / "clip.html"

    # 단계 배포의 의미를 리포트에도 명시 (user 2026-07-06): 서비스가 처리한 클립은
    # result.json의 products_open이 진실 — 닫힌 제품 섹션은 숨기지 않고 🔒 접힘으로
    # "열고 닫음"을 보이게 한다 (내부 연구 뷰로는 펼쳐 볼 수 있음; Result에는 미반출).
    # result.json 없는 클립(순수 연구 런) = 전체 열림.
    res = _load(cdir / "result.json") or {}
    opened = set(res["products_open"]) if res.get("products_open") is not None else None

    def _section(product: str, title: str, body: list[str]) -> str:
        inner = "".join(body)
        if opened is None or product in opened:
            return f"<h2>{title}</h2>" + inner
        return ("<details style='opacity:.75'><summary style='cursor:pointer'>"
                f"<h2 style='display:inline'>{title}</h2> "
                "<span class=chip>🔒 미오픈 — 단계 배포 (내부 연구 뷰 · Result 미반출)</span>"
                f"</summary>{inner}</details>")

    B: list[str] = [f"<style>{_CSS}</style>", f"<h1>momentscan · {html.escape(clip_id)}</h1>"]
    src = html.escape(str(prov.get("source_uri", "")))
    B.append(f"<div class=meta>{src}{' · ' if src else ''}processed {html.escape(str(prov.get('processed_at_iso', '—')))}"
             + (f" · <a href='inspect/clip.html'>inspector 열기 (왜 이렇게 뽑혔나)</a>" if inspect_html.exists() else "")
             + "</div>")

    # ── PORTRAITS ────────────────────────────────────────────────────────────
    sec: list[str] = []
    riders = pj.get("riders", {})
    if not riders:
        sec.append("<div class=warn>portrait 산출물 없음 (portrait 스테이지 미실행?)</div>")
    for sid, r in riders.items():
        cards = []
        rep = r.get("rep") or {}
        if r.get("rep_file"):
            cards.append(f"<div class=card><img src='portraits/{html.escape(r['rep_file'])}'>"
                         f"<div class=cap><b>rep</b> · f{rep.get('frame_idx', '?')}"
                         f" · warm {rep.get('terms', {}).get('warm', '—')}</div></div>")
        for e in r.get("set") or []:
            if e.get("file"):
                cards.append(f"<div class=card><img src='portraits/{html.escape(e['file'])}'>"
                             f"<div class=cap>{html.escape(e.get('view', '?'))} · f{e.get('frame_idx', '?')}</div></div>")
        sec.append(f"<div class=kv>subject {html.escape(str(sid))} <span class=chip>{html.escape(str(r.get('role')))}</span>"
                   f" admit {r.get('n_admit')}/{r.get('n_total')}</div><div class=grid>{''.join(cards)}</div>")
    B.append(_section("portrait", "PORTRAIT — 대표컷 · 뷰 세트", sec))

    # ── HIGHLIGHTS ───────────────────────────────────────────────────────────
    sec = []
    if hls:
        sec.append("<div class=grid>" + "".join(
            f"<div class=card><video src='highlights/{html.escape(p.name)}' controls muted></video>"
            f"<div class=cap>{html.escape(p.name)}</div></div>" for p in hls) + "</div>")
    else:
        sec.append("<div class=warn>highlight mp4 없음 (`momentscan viz <clip>`이 렌더)</div>")
    B.append(_section("highlight", "HIGHLIGHT — 세그먼트 클립", sec))

    # ── LIKENESS ─────────────────────────────────────────────────────────────
    sec = []
    for sid, r in (lk.get("riders") or {}).items():
        fid = r.get("face_id") or {}
        fa = r.get("fashion") or {}
        worn = [k for k in ("mask", "hat") if fa.get(k)] + ([fa["eyewear"]] if fa.get("eyewear") not in (None, "none") else [])
        # 의상 컬러 팔레트 (Cat W 포팅) — 디자이너용 스와치 칩
        ci = r.get("color_identity")
        chips = ""
        if isinstance(ci, dict):
            for k in ("primary", "secondary", "highlight"):
                v = ci.get(k)
                if isinstance(v, dict) and v.get("hex"):
                    chips += (f"<span title='{k} {html.escape(v['hex'])}' style='display:inline-block;"
                              f"width:15px;height:15px;background:{html.escape(v['hex'])};"
                              f"border-radius:3px;border:1px solid #444;vertical-align:-3px;margin:0 2px'></span>")
            chips = f" · 팔레트 {chips} (다양성 {ci.get('palette_diversity', '—')})" if chips else ""
        sec.append(f"<div class=kv>subject {html.escape(str(sid))} <span class=chip>{html.escape(str(r.get('role')))}</span>"
                   f" · 관측 <b>{r.get('n_obs', '—')}</b>"
                   f" · 재현성 drift <b>{r.get('split_half_drift', '—')}</b>"
                   f" · face_id coherence <b>{fid.get('coherence_mean', '—')}</b> (n={fid.get('n_emb', '—')})"
                   f" · 착용 <b>{html.escape(', '.join(worn) or '없음')}</b>{chips}</div>")
    if not lk.get("riders"):
        sec.append("<div class=warn>likeness.json 없음</div>")
    B.append(_section("likeness", "LIKENESS — 방문-스코프 외형 ID", sec))

    # ── 산출물 tier 지도 (R12) — 이 디렉토리의 각 파일은 무엇인가, 선언이 답한다 ──
    from momentscan.analyzers import TIERS, classify_clip_files
    tiers_map = classify_clip_files(cdir)
    sec = []
    for tier in (*TIERS, "unclassified"):
        members = sorted(f for f, t in tiers_map.items() if t == tier)
        if members:
            sec.append(f"<div class=kv><span class=chip>{tier}</span> "
                       f"{html.escape(' · '.join(members))}</div>")
    B.append(_section("tiers", "산출물 tier 지도 — substrate/product/surface/ops (R12)", sec))

    out = cdir / "index.html"
    out.write_text("<!doctype html><meta charset='utf-8'>"
                   f"<title>momentscan · {html.escape(clip_id)}</title>" + "".join(B), encoding="utf-8")
    return {"clip_id": clip_id, "ok": True, "report": str(out),
            "elapsed_s": round(time.perf_counter() - t0, 3)}
