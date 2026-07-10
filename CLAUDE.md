# momentscan — 세션 부트 (p981.scan)

p981 우산의 멤버 **MomentScan**. 비디오 → 타겟 고객 관측 → likeness/portrait/highlight
추출. 독립 git·메모리 부팅 (이 파일 = 결정적 오리엔테이션 / 일화적 맥락 = 메모리 MEMORY.md).

## 세션 시작 의식
1. `../mailbox/momentscan.md`의 `## 열림` 확인 → bead 회신은 우산 repo 커밋
   (`git -C ~/repo/p981 ...`). 내부 R/rq 작업은 인박스에 복제하지 않는다.
2. 메모리 `session-resume-point`로 직전 맥락 복원.
3. **이 세션의 작업 트랙(R/E/rq ID) 하나를 선언**하고 그 범위에서 작업한다.
   트랙 밖 발견은 고치지 말고 원장(refactor-plan)/인박스에 기록만.

## 문서 사슬 (읽기 순서)
ids(정본 `~/repo/p981/ids.md` · 로컬 `docs/ids.md`=스텁) → `docs/contracts.md`(C1~C12)
→ `docs/refactor-exec-plan.md`(헛점 L1~L13 · 작업 R0~R17) → `docs/visualstack-redesign.md`.
단축코드: 스테이지 M01~M12 · 게이트 V01~V05 · 제품 P1~P3 · 계약 C1~C12.

## 하드 룰
- **트랙-스코프**: 비자명 코드 트랙(R/E/rq)은 `track/<id>` 브랜치에서 작업, 완료
  기준(verify+특성화 green) 통과 시 **머지로 통째 착지**, 되돌림=머지 리버트 한 방.
  문서·오타·ops(서버·mailbox)는 main 직행. ⚠stash(output/)는 브랜치를 안 탄다 —
  산출물 재계산이 걸린 트랙은 branch-scoped `--out`, 공유 코퍼스 갱신은 머지 후.
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
