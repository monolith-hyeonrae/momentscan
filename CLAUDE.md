# momentscan — 세션 부트 (p981.scan)

p981 우산의 멤버 **MomentScan**. 비디오 → 타겟 고객 관측 → likeness/portrait/highlight
추출. 독립 git·메모리 부팅 (이 파일 = 결정적 오리엔테이션 / 일화적 맥락 = 메모리 MEMORY.md).

## 세션 시작 의식
1. `../mailbox/momentscan.md`의 `## 열림` 확인 → bead 회신은 우산 repo 커밋
   (`git -C ~/repo/p981 ...`). 내부 R/rq 작업은 인박스에 복제하지 않는다.
2. 메모리 `session-resume-point`로 직전 맥락 복원.

## 문서 사슬 (읽기 순서)
ids(정본 `~/repo/p981/ids.md` · 로컬 `docs/ids.md`=스텁) → `docs/contracts.md`(C1~C12)
→ `docs/refactor-exec-plan.md`(헛점 L1~L13 · 작업 R0~R17) → `docs/visualstack-redesign.md`.
단축코드: 스테이지 M01~M12 · 게이트 V01~V05 · 제품 P1~P3 · 계약 C1~C12.

## 하드 룰
- 커밋 **co-author 트레일러 금지**(user 명시). 커밋 메시지 `-m`에 백틱 금지(셸 치환
  사고 이력) → 여러 줄은 heredoc `-F`.
- 비자명 변경은 **커밋 전 verify**(registry/api/replay 또는 특성화). 실패 시 중단·보고.
- 계약(C·p981.if.*)은 심판 — additive만 무버전, 의미/형태 변경 = 버전 + 소비자 동시.
- gen·회사 앱은 **p981.if.\*만 소비**(scan 내부 mod 직접 의존 금지). 회사 대면 = 출력·openapi.

## 실행
- `momentscan run <clip> [--only <stage> ...] [--force] [--source <video>]`
- `momentscan server start|status|stop [--port N]` (장기 기동 = `setsid nohup … &`, 세션 teardown 방어)
- `momentscan verify registry|api|replay|doctor` · `momentscan map|report|inspect|viz`
- venv = `.venv`(uv sync). 임계값/정책은 preset(C9 자리) 지향, 코드 산개는 R8 인벤토리 참조.
