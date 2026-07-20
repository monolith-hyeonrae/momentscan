"""perception — 관측 계층. 픽셀에서 "믿을 수 있는 읽기"까지, 제품 이전의 모든 것.

관측 사슬 (누구를 → 무엇을 → 어떻게 읽나 → 믿을 수 있나):
  subjects/     누구를 — 검출·추적·귀속·튜블릿·크롭 (관측의 주체 constitution)
  extraction/   무엇을 — 프레임에서 원신호 추출 (features·scene·parse·fashion·headpose·ingest)
  readings/     어떻게 읽나 — 원신호의 해석 (emotion·pose·geometry·signals; 정준 프레임 계약)
  gates.py      믿을 수 있나 — 판정 사다리(admit/reject/route). A″에서 pipeline 을 떠나
                여기로: 게이트는 순수 실행 기계가 아니라 readings 계층의 이진 판별기다(user 판정).

단위기술 회전 지대 (rotating substrate): 백엔드는 갈린다 — MediaPipe↔6DRepNet(pose),
HSEmotion↔LibreFace(emotion), SegFormer→랜드마크 soft-Gaussian(quality). 계약(정준
좌표·registry FIELDS)은 얼고, 그 아래 모델은 eval 로 교체된다.

위임 브리프 지대: 이 계층의 산출물이 products 의 원료다 — likeness=face_recipe,
portrait=미학 게이트, highlight=WHEN/WHICH. perception 은 제품 정책을 모른다(무지가 계약).
"""
