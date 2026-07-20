"""serve — 외부 접점(항구). 시스템이 바깥 세계와 만나는 네 개의 문:

  service.py   C1 HTTP 면 (Job/Result 실행기 — 회사 게이트웨이가 직접 옴)
  company.py   회사 디스패치 방언 어댑터 (cju-activity-video-control shim)
  eureka.py    서비스 디스커버리 등록 + OAuth2 JWT (TokenProvider)
  daemon.py    UDS 웜 제어면 (로컬 연구/운영자 도구 — 관측 레인 밖)

전원 visualserve(L4) 졸업석 예약 — 이 패키지 경계가 졸업 절단선의 리허설이다
(구조 감사 접수 #1, 2026-07-15). 로거 이름은 구 경로(momentscan.service 등)를
유지한다 — 관측 정체성(Loki 라벨·대시보드)은 물리 배치와 독립.
"""
