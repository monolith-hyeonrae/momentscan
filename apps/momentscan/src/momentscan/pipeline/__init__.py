"""pipeline — 실행 기계. 등기(registry)와 그 집행(runner)·skip 정책(freshness)·
판정(gates)·렌더(graph)가 한 지붕: 트리가 "무엇이 어떻게 도는가"에 답한다 (접수 #1·#4·#6).
"engine" 낱말은 제품 엔진(=질문)에게 돌려줬다 (T6) — 이 패키지는 실행 파이프라인이다.

  registry.py    선언 지도 — 생산자 카탈로그 + PRODUCTS 수직 읽기맵 (단일 권위; 구 analyzers.py)
  runner.py      DAG 순서 집행기 (RUNNERS + resumable skip; 구 pipeline.py — 말더듬 해소)
  freshness.py   산출물 신선도 = 런의 속성 (verify에서 이주 — 검증 도구가 아니라
                 매 런의 실행 기계였음; 구조 감사 #4)
  gates.py       판정 사다리 — 게이트 카탈로그(측정 위의 admit/reject/route; R10 스테이지)
  graph.py       선언 그래프의 한 장 렌더 (legibility spine)

전원 visualpath(L3) ArtifactNode 졸업석 예약 — 이 경계가 R16/R17의 절단선.
"""
