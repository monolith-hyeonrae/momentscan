"""Artifact tiers — the logical status of every stash file (R12, 2026-07-15).

산출물 tier: 물리 이동 없이 논리 구분을 선언한다.
  substrate = 측정·공유 기판(재계산 가능한 중간물)
  product   = 제품 산출(egress 후보)
  surface   = 사람용 렌더
  ops       = 런 기록/운영 흔적
이 선언이 훗날 물리 재배치의 지도가 된다(지금 배치를 정당화하는 게 아니라 실제
지위를 정직하게 기록). ARTIFACT_TIERS 는 ANALYZERS 산출물에서 파생 + 비-분석기
산출물(EXTRA_ARTIFACT_TIERS)의 합집합 — per-clip manifest.json 과 report 4그룹
렌더가 같은 지도(classify_clip_files)를 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from momentscan.infra.pipeline.registry.analyzers import ANALYZERS

TIERS = ("substrate", "product", "surface", "ops")

# artifact → tier 지도. 분석기 산출물은 선언에서 파생, 비-분석기 산출물(공유 흔적·
# 사람용 렌더·런 기록)은 여기 명시.
EXTRA_ARTIFACT_TIERS: dict[str, str] = {
    # gate_trace.parquet tier는 gates 분석기 선언에서 파생 (R10) — 여기 명시 불필요.
    "candidates.jsonl": "substrate",        # 공유 채점 로그 (select·portrait 공동 기록)
    "emotion_frame.parquet": "substrate",   # per-frame valence 관측 흔적
    "stitch.json": "substrate",             # re-id 병합 기록
    "landmarks.parquet": "substrate",       # (선언에도 있으나 명시 — features 백엔드가 기록, D4)
    "highlights/": "product",               # 렌더된 하이라이트 세그 mp4
    "detect.mp4": "surface",                # 사람용 오버레이 렌더 (리포트 썸네일 폴백)
    "index.html": "surface", "inspect/": "surface",
    "job.json": "ops", "run.json": "ops", "provenance.json": "ops",
    "result.json": "ops", "manifest.json": "ops",
    "process_trace.jsonl": "ops", "process_timeline.png": "ops",
    "source_cache/": "ops", "eval/": "ops",
}

ARTIFACT_TIERS: dict[str, str] = (
    {a.artifact: a.tier for a in ANALYZERS if a.artifact != "inline"} | EXTRA_ARTIFACT_TIERS)


def classify_clip_files(cdir) -> dict[str, str]:
    """클립 디렉토리 최상위 항목 → tier. 미지 항목은 'unclassified'(정직) —
    manifest.json(파이프라인 기록)과 report 하단 지도가 같은 함수를 쓴다."""
    out: dict[str, str] = {}
    for p in sorted(Path(cdir).iterdir()):
        key = p.name + "/" if p.is_dir() else p.name
        out[key] = ARTIFACT_TIERS.get(key, "unclassified")
    return out
