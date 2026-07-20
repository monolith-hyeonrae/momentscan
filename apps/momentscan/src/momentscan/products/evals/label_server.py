"""Pairwise labeling dashboard ([[pairwise-labeling-principle]]).

``momentscan label`` serves A-vs-B comparisons with the product question on
screen ("외형 레퍼런스로 더 좋은 한 장은?" / "더 임팩트 있는 순간은?").
Highlight pairs ANIMATE (±1s frame cycle) — moments live in sequences, not
stills. Keys: a / b / t(ie) / p(rev). Verdicts → eval/pair_verdicts.jsonl,
scored by ``momentscan verify eval`` as system-claim agreement. Pairs are generated
on first run (evalharness.make_pairs).
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>momentscan · pairs</title>
<style>
body{background:#0A0C10;color:#EDEAE1;font-family:monospace;margin:0;padding:16px;text-align:center}
#q{font-size:18px;margin:8px;color:#E0AC5C}
.row{display:flex;justify-content:center;gap:14px}
.panel{cursor:pointer;border:2px solid #333;max-width:46vw}
.panel img{width:100%;display:block}
.panel .tag{padding:5px;font-size:14px;color:#999}
.panel:hover{border-color:#8FD597}
.meta{margin:8px;font-size:13px;color:#777}
button{background:#1a1f28;color:#EDEAE1;border:1px solid #444;padding:8px 22px;margin:5px;font-family:monospace;cursor:pointer}
#bar{height:4px;background:#8FD597;width:0%;margin-bottom:10px;transition:width .2s}
</style></head><body>
<div id="bar"></div><div id="q"></div>
<div class="row">
 <div class="panel" onclick="pick('a')"><img id="ia"><div class="tag">A (key: a)</div></div>
 <div class="panel" onclick="pick('b')"><img id="ib"><div class="tag">B (key: b)</div></div>
</div>
<div><button onclick="pick('tie')">tie (t)</button><button onclick="prev()">← prev (p)</button>
<button onclick="next()">skip (s)</button></div>
<div class="meta" id="meta"></div>
<script>
let items=[],i=0,anim=null,tick=0;
const Q={likeness:"외형 측정용 레퍼런스로 더 좋은 한 장은? (정면·무표정·이목구비 선명)",
         profile:"외형 측정용 레퍼런스로 더 좋은 한 장은? (정면·무표정·이목구비 선명)",  // v0 product명 호환
         portrait:"포트레이트로 더 좋은 한 장은? (이 사람의 대표 얼굴 — 멋진 표정·조명, 앵글·사이드 허용)",
         highlight:"더 임팩트 있는 '순간'은? (장면·상황의 특수성, 움직임 포함)",
         highlight_segment:"더 좋은 하이라이트 클립은? (순간의 가치 — 두 클립 모두 반복 재생)",
         highlight_boundary:"잘림(시작·끝)이 더 자연스러운 클립은? (같은 순간, 다른 경계)"};
async function load(){items=await(await fetch('/api/pairs')).json();
 if(!items.length){document.getElementById('q').textContent=
   '쌍이 없습니다 — 서버를 레포 루트에서 올바른 --out 경로로 다시 실행하세요';return;}
 i=items.findIndex(x=>!x.winner); if(i<0)i=0; show();}
function frameURL(it,f,off){return `/api/frame?clip=${it.clip_id}&f=${f+off}`;}
function show(){clearInterval(anim);const it=items[i];
 document.getElementById('q').textContent=Q[it.product];
 document.getElementById('meta').textContent=
  `[${i+1}/${items.length}] ${it.clip_id} · ${it.rider_role} · ${it.product}`+
  (it.winner?` · 현재: ${it.winner}`:'');
 document.getElementById('bar').style.width=(100*items.filter(x=>x.winner).length/items.length)+'%';
 if(it.a_span){let ta=0,tb=0;            // segment lane: each side loops its own span
  const la=it.a_span[1]-it.a_span[0],lb=it.b_span[1]-it.b_span[0];
  document.getElementById('ia').src=frameURL(it,it.a_span[0],0);   // first frame now (no 170ms blank)
  document.getElementById('ib').src=frameURL(it,it.b_span[0],0);
  anim=setInterval(()=>{ta=(ta+1)%la;tb=(tb+1)%lb;
   document.getElementById('ia').src=frameURL(it,it.a_span[0],ta);
   document.getElementById('ib').src=frameURL(it,it.b_span[0],tb);},170);}
 else if(it.product==='highlight'){tick=-6;
  anim=setInterval(()=>{tick=tick>6?-6:tick+1;
   document.getElementById('ia').src=frameURL(it,it.a_frame,tick);
   document.getElementById('ib').src=frameURL(it,it.b_frame,tick);},170);}
 else{document.getElementById('ia').src=frameURL(it,it.a_frame,0);
      document.getElementById('ib').src=frameURL(it,it.b_frame,0);}}
async function pick(w){const it=items[i];it.winner=w;
 await fetch('/api/pick',{method:'POST',body:JSON.stringify(it)});next();}
function next(){if(i<items.length-1){i++;show();}else show();}
function prev(){if(i>0){i--;show();}}
document.onkeydown=e=>{if(e.key==='a')pick('a');if(e.key==='b')pick('b');
 if(e.key==='t')pick('tie');if(e.key==='s')next();if(e.key==='p')prev();};
load();
</script></body></html>"""


# lane → pair-generation config; suffix keys files so the frozen default lane
# (pairs.jsonl / pair_verdicts.jsonl) is never touched by a new product lane.
_LANES: dict[str, dict] = {
    "default": {},
    "portrait": {"products": ("portrait",), "cross_vs": "likeness",
                 "out_name": "pairs_portrait.jsonl", "roles": ("main",)},
    "segment": {},   # E010 — make_segment_pairs (span playback, 경계의 자)
}


class _Handler(BaseHTTPRequestHandler):
    out_root: Path
    lane: str = "default"

    @property
    def _suffix(self) -> str:
        return "" if self.lane == "default" else f"_{self.lane}"

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")   # labeling page changes — never cache stale JS
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        ev = self.out_root / "eval"
        if u.path == "/":
            self._send(_PAGE.encode(), "text/html; charset=utf-8")
        elif u.path == "/api/pairs":
            pp = ev / f"pairs{self._suffix}.jsonl"
            if not pp.exists():
                if self.lane == "segment":
                    from momentscan.products.evals.harness import make_segment_pairs
                    make_segment_pairs(self.out_root)
                else:
                    from momentscan.products.evals.harness import make_pairs
                    make_pairs(self.out_root, **_LANES[self.lane])
            pairs = [json.loads(ln) for ln in pp.read_text(encoding="utf-8").splitlines() if ln.strip()]
            vp = ev / f"pair_verdicts{self._suffix}.jsonl"
            done = {}
            if vp.exists():
                for ln in vp.read_text(encoding="utf-8").splitlines():
                    if ln.strip():
                        r = json.loads(ln)
                        done[(r["clip_id"], r["track_id"], r["product"], r["a_frame"], r["b_frame"])] = r["winner"]
            for p in pairs:
                k = (p["clip_id"], p["track_id"], p["product"], p["a_frame"], p["b_frame"])
                if k in done:
                    p["winner"] = done[k]
            self._send(json.dumps(pairs, ensure_ascii=False).encode())
        elif u.path == "/api/frame":
            q = parse_qs(u.query)
            clip, f = q["clip"][0], max(0, int(q["f"][0]))
            cap = cv2.VideoCapture(str(self.out_root / clip / "detect.mp4"))
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            cap.release()
            buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])[1] if ok else b""
            self._send(bytes(buf), "image/jpeg")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/api/pick":
            self.send_response(404); self.end_headers(); return
        item = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        vp = self.out_root / "eval" / f"pair_verdicts{self._suffix}.jsonl"
        rows = [json.loads(ln) for ln in vp.read_text(encoding="utf-8").splitlines() if ln.strip()] if vp.exists() else []
        key = (item["clip_id"], item["track_id"], item["product"], item["a_frame"], item["b_frame"])
        rows = [r for r in rows
                if (r["clip_id"], r["track_id"], r["product"], r["a_frame"], r["b_frame"]) != key]
        rows.append(item)
        vp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        self._send(b"{}")


def serve_labels(out_root, *, port: int = 8901, lane: str = "default") -> None:
    if lane not in _LANES:
        raise ValueError(f"unknown lane {lane!r} — one of {sorted(_LANES)}")
    root = Path(out_root).resolve()
    _Handler.out_root = root
    _Handler.lane = lane
    n_clips = len(list(root.glob("*/candidates.jsonl")))   # sanity: wrong cwd → 0
    print(f"pairwise labeling [{lane}] → http://localhost:{port}  (a/b=선택 t=tie s=skip p=prev)")
    print(f"  out_root = {root}  ({n_clips} clips)")
    if n_clips == 0:
        print(f"  ⚠️  candidates.jsonl이 없습니다 — --out 경로/실행 위치를 확인하세요 (지금 cwd: {Path.cwd()})")
    ThreadingHTTPServer(("127.0.0.1", port), _Handler).serve_forever()
