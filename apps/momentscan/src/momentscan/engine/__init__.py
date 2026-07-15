"""engine — 실행 기계. 선언(analyzers)과 그 집행(pipeline)·skip 정책(freshness)·
렌더(graph)가 한 지붕: 트리가 "무엇이 어떻게 도는가"에 답한다 (접수 #1·#4).

  analyzers.py   선언 지도 — 생산자 카탈로그 + PRODUCTS 수직 읽기맵 (단일 권위)
  pipeline.py    DAG 순서 집행기 (RUNNERS + resumable skip)
  freshness.py   산출물 신선도 = 런의 속성 (verify에서 이주 — 검증 도구가 아니라
                 매 런의 실행 기계였음; 구조 감사 #4)
  graph.py       선언 그래프의 한 장 렌더 (legibility spine)

전원 visualpath(L3) ArtifactNode 졸업석 예약 — 이 경계가 R16/R17의 절단선.
"""
