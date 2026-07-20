"""infra — 제품 무관 시공(施工). 관측·가치판단이 아니라 "돌게 하는 배관"이 산다.

공유 운명 (A″, 2026-07-16/17): 이 그룹은 함께 떠난다 — visualstack 기판으로의
졸업석(R16/R17 절단선)을 한 묶음으로 예약한 멤버들이다. perception/products 가
연구로 들끓는 동안 infra 는 계약이 얼면 통째 하차한다.

방향 표 (이 경계를 넘는 의존은 한 방향으로만 읽힌다):
  inbound   cli/     사람 대면 관문 (verb → 파이프라인·surface 호출)
            serve/   회사 대면 관문 (Job/Result·Eureka·company shim)
  outbound  store/   stash·ports·telemetry — 지속·계약·관측 (IO 배관)
            media.py 픽셀 트랜스코드 (ffmpeg h264/letterbox)
  internal  pipeline/ registry·runner·freshness·graph — 실행 기계

의존 규칙 (한 줄): inbound(cli·serve)가 outbound(store·media)를 아는 것은
JobRunner 이음매를 경유한다 — 관문은 배관을 직접 얽지 않고 잡(job) 계약으로 만난다.
"""
