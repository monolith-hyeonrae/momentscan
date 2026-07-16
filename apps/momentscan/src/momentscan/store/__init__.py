"""store — 산출물 저장 계열 (visualstash L2 졸업석 예약, 접수 #1).

  stash.py      per-clip 산출물 read/write의 단일 홈 (최대 허브 — fold-store에서
                artifact registry 테이블로 접힘 예정)
  ports.py      plugin-대면 타입 계약 (FeatureSource·Tubelet·TrackFeatures —
                momentscan 최상위 재수출로 소비: `from momentscan import Tubelet`)
  telemetry.py  후보 로그 등 관측 흔적 계약

freshness INFRA 제외 대상 — IO 배관 수정이 전 산출물을 stale시키지 않게
(pipeline/freshness.py INFRA={"store"}가 이 패키지를 가리킨다).
"""
