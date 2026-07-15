"""Doctor — the first-15-minutes check: are the external pieces in place?

A CHECKER, not a fetcher — several backends are license-gated (insightface
weights are research/non-commercial; DINOv3 is gated on HF), so silently
downloading them would hide an obligation. Each row says what it serves and how
to obtain it. Import-light: path/spec probes only, no model loads.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

_HF = Path.home() / ".cache" / "huggingface" / "hub"


def _hf(repo: str) -> bool:
    return (_HF / ("models--" + repo.replace("/", "--"))).is_dir()


def checks() -> list[dict]:
    """→ [{name, ok, serves, hint}] — the full external-dependency census."""
    from momentscan.readings.geometry import CANONICAL_OBJ
    from momentscan.extraction.headpose import DEFAULT_ONNX
    ins = Path.home() / ".insightface" / "models"
    rows = [
        # binaries
        dict(name="ffmpeg", ok=shutil.which("ffmpeg") is not None,
             serves="crops·highlight·inspector 인코딩", hint="apt install ffmpeg"),
        # python stacks (per isolation rung)
        dict(name="onnxruntime", ok=importlib.util.find_spec("onnxruntime") is not None,
             serves="detect·headpose6d", hint="uv sync"),
        dict(name="mediapipe", ok=importlib.util.find_spec("mediapipe") is not None,
             serves="landmarks(features 스테이지)·parse 오벌", hint="uv sync --extra …(specialist45d)"),
        dict(name="torch+transformers", ok=all(importlib.util.find_spec(m) is not None
                                               for m in ("torch", "transformers")),
             serves="parse(SegFormer)·fashion·scene·highlight-lang", hint="uv sync"),
        dict(name="visualbus/visualpath", ok=importlib.util.find_spec("visualbus") is not None,
             serves="ingest·detect 버스", hint="workspace 의존 — uv sync"),
        # model weights (license-gated ones say so)
        dict(name="buffalo_l (insightface)", ok=(ins / "buffalo_l").is_dir(),
             serves="detect: 얼굴검출+ArcFace 임베딩",
             hint="⚠ 비상업 연구 라이선스 — insightface model zoo에서 수동 취득"),
        dict(name="6DRepNet onnx", ok=Path(DEFAULT_ONNX).exists(),
             serves="headpose6d: 프로필 포즈", hint=f"→ {DEFAULT_ONNX}"),
        dict(name="canonical_face_model.obj", ok=Path(CANONICAL_OBJ).exists(),
             serves="geometry: 정준 프레임 템플릿", hint=f"MediaPipe 저장소 → {CANONICAL_OBJ}"),
        dict(name="SegFormer face-parsing", ok=_hf("jonathandinu/face-parsing"),
             serves="parse: 착용물 presence", hint="첫 실행 시 HF 자동 다운로드"),
        dict(name="FashionCLIP", ok=_hf("patrickjohncyh/fashion-clip"),
             serves="fashion: 액세서리 타입", hint="첫 실행 시 HF 자동 다운로드"),
        dict(name="DINOv3", ok=any(_HF.glob("models--facebook--dinov3*")),
             serves="scene: 장면 임베딩", hint="⚠ HF gated — huggingface-cli login 후 접근 신청"),
        dict(name="CLIP ViT-L", ok=_hf("openai/clip-vit-large-patch14"),
             serves="highlight-lang: 장면 서술", hint="첫 실행 시 HF 자동 다운로드"),
        dict(name="Qwen2.5-VL-3B", ok=any(_HF.glob("models--Qwen--Qwen2.5-VL-3B*")),
             serves="highlight-lang: LLM-judge", hint="첫 실행 시 HF 자동 다운로드"),
        dict(name="boto3", ok=importlib.util.find_spec("boto3") is not None, optional=True,
             serves="serve(HTTP): s3:// 소스 반입·결과 반출 (선택 — AWS 배포만, 로컬 알파 불필요)",
             hint="uv pip install boto3 — AWS 노드에서만"),
    ]
    return rows


def render_text() -> int:
    rows = checks()
    miss = [r for r in rows if not r["ok"] and not r.get("optional")]   # 선택 의존은 경고만
    print("── momentscan verify doctor — 외부 의존 점검 (checker, not fetcher) ──")
    for r in rows:
        mark = "✓" if r["ok"] else ("○" if r.get("optional") else "✗")
        print(f"  {mark} {r['name']:28s} {r['serves']}")
        if not r["ok"]:
            print(f"      → {r['hint']}")
    print(f"\n  {len(rows) - len(miss)}/{len(rows)} 준비됨"
          + ("" if not miss else f" · 누락 {len(miss)} (위 힌트 참조; gated 모델은 자동 취득 안 함)"))
    return 0 if not miss else 1
