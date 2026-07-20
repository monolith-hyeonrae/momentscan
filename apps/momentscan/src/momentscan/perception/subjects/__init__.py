"""Subject constitution — the secret: "픽셀 스트림에서 누구를, 어디서 볼 것인가"
(who to observe, and where). ONE chain, head to tail: detect (얼굴 검출 + IoU 트래킹 +
ArcFace 임베딩) -> stitch (클립-끝 re-id 병합) -> attribute (rider_role = 깊이 투표) ->
tubelets (THE boundary contract: extractors read tubelets, never raw detections) ->
crops (the tube's clean pixels). detect은 T6에서 extraction/에서 이주 — 대상-확립 사슬의
머리이지 순수 측정이 아니다 (접수 #9). Membership: "does it change when the subject
contract changes?" See ARCHITECTURE.md."""
