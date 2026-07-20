"""Frontend — 구독자: persisted observability payload 위 렌더러 (inspector, label UI).
예외 자백: cards.py 2곳이 products.select 의 frame_scores/rolling_median 을 재계산한다
(단일홈 임포트라 Parnas 합법이나 "persisted payload 위 순수 렌더러" 계약 위반) — 처방은
G10 scores.parquet 예약석(energy 재편이 채널 안정시킨 직후), 과도기 안전망은 freshness ⚠STALE.
"""
