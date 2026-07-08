# ID Registry v2 — p981 계층 체계

**v2 (2026-07-07)**: momentscan 단독 체계(v1: M/V/P/C)를 **portrait981 프로젝트
전체 구조**로 확장. 회사 프로젝트 = **p981**(portrait981); 그 아래 두 소프트웨어 —
**p981.scan**(MomentScan: frozen model 기반 관측·추출)과 **p981.gen**(MomentGen:
diffusion 계열 품질·연출). scan의 출력은 **회사 앱/키오스크**(외부 소비자)와
**p981.gen**(user 관리)이 소비한다. v1의 M/V/P 번호는 **단축코드로 영구 보존**
(기존 문서·커밋·메모리의 참조가 깨지지 않게).

## 규율

- **ID는 순수 식별자** — 상태(experimental/deprecated)·버전·라이선스는 ID가 아니라
  **필드**로. ID 불변·재사용 금지·개명 무추종(v1 규율 유지).
- **안정 경계 = 의미 기반 계층 ID** (scan 모듈: 연구 영역과 1:1이라 안 사라짐) /
  **유동 경계 = 불투명 키 + 사람용 이름** (gen 스타일, model 자산: 갈아끼워짐).
- **모듈 슬롯 ≠ model 자산**: 슬롯은 고정, 가중치는 `binds: mdl-XXXX @ver`로 교체.
- **leaf 토큰 재사용**: `fashion` 하나로 mod(모듈)·rq(연구 트랙)·산출물이 grep
  한 방에 잡힌다.
- 타입: `mod`(모듈) `gate`(validity) `if`(계약/인터페이스) `mdl`(frozen model 자산)
  `sty`(gen 스타일) `rq`(연구 트랙) `dep`(종속).

## 레포 토폴로지 ≠ 논리 네임스페이스 (2026-07-07 확정)

scan/gen은 **다른 GPU 서버·다른 레포**로 갈 가능성이 높다(user). 그래도 p981
네임스페이스는 유지 — ID는 "시스템 전체에서 무엇인가"지 "코드가 어디 있는가"가
아니며, 물리적으로 떨어질수록 공통 논리 언어가 필요하다. 달라지는 것 하나:
**p981.if.*가 네트워크를 건너는 와이어 계약으로 격상**된다.

**레지스트리 소유권 분할**: scan 레포=p981.scan.*(mod/gate/mdl/rq) 소유 ·
gen 레포=p981.gen.*(sty) 소유 · **p981.if.*=중립 지대**(p981-contracts — 스키마만
담는 소형 레포, 두 쪽이 버전 핀으로 참조; gen 레포가 실체화될 때 분리, 그 전
임시 홈=momentscan/docs/api). gen 레지스트리에 p981.scan.*는 **절대 등장하지
않는다** — 물리 분리가 이 규칙을 권장에서 강제로 바꾼다.

## p981.if — 프로젝트-레벨 **와이어 계약** (scan 생산 → gen·회사 앱 소비)

제품 = 단순 출력이 아니라 **두 시스템을 잇는 계약** → 서브시스템이 아닌 프로젝트
레벨. 스키마 버전은 별도 필드(@schema)로 — 소비자가 의존하는 것이 곧 이 필드.
**와이어 형태 = 작은 매니페스트 + 큰 아티팩트 참조**(GPU 비디오 워크로드 =
비동기·큐 전달) — C1 Result가 이미 이 모양(transport-agnostic·outputs=uri 맵·멱등).
버전 규율: additive=minor(1.0→1.1)·파괴적=major(→2.0), 소비자는 범위 핀
(`>=1.0 <2.0`) — 세부는 contracts.md C1 참조.

| ID | 단축 | @schema | 스키마 홈 | 소비자 |
|---|---|---|---|---|
| p981.if.likeness | P1 | momentscan.likeness/**v1 (동결)** | contracts.md §C11 | p981.gen(face_recipe→3D)·회사 앱 |
| p981.if.portrait | P2 | momentscan.portrait/v0 (미동결) | R4에서 도장 | 회사 앱/키오스크 |
| p981.if.highlight | P3 | momentscan.highlight/v0 (미동결) | R4에서 도장 | 회사 앱/키오스크·p981.gen(연출 소재) |

배송 transport = C1 Job/Result(openapi.yaml). **gen은 scan 내부(mod)에 절대 직접
의존하지 않는다 — if.*에만**: `dep: p981.gen → p981.if.likeness [data, required]`.
scan 내부를 아무리 재편해도 계약만 지키면 gen·회사 앱은 무영향.

## p981.scan.mod — 관측·추출 모듈 (의미 기반; 파이프라인 의존 순)

| 정식 ID | 단축 | 코드명 | 산출물 |
|---|---|---|---|
| p981.scan.mod.face_detect | M01 | detect | detections.parquet · landmarks.parquet |
| p981.scan.mod.stitch | M02 | stitch | (detections 내 subject_id) |
| p981.scan.mod.attribute | M03 | attribute | attribution.json |
| p981.scan.mod.tubelet | M04 | tubelets | tubelets.parquet |
| p981.scan.mod.scene | M05 | scene | scene.parquet |
| p981.scan.mod.features | M06 | features | features/*.parquet (46-dim) |
| p981.scan.mod.crops | M07 | crops | crops/manifest.json + s*.mp4 |
| p981.scan.mod.parse | M08 | parse | parse.parquet (조명·presence·skin) |
| p981.scan.mod.fashion | M09 | fashion | fashion.json (타입·컬러·헤어) |
| p981.scan.mod.head_pose | M10 | headpose6d | headpose.parquet |
| p981.scan.mod.emotion | M11 | emotion | emotion.json |
| p981.scan.mod.select | M12 | select | select.json · candidates.jsonl |

## p981.scan.gate — validity 게이트 (gate_trace.parquet)

| 정식 ID | 단축 | 원리 |
|---|---|---|
| p981.scan.gate.exposure | V01 | ISO29794-5 휘도 엔트로피 (tone-invariant) |
| p981.scan.gate.blur | V02 | 0.5×median floor + smear |
| p981.scan.gate.pose | V03 | 3-way quantizer (MP⊕6D) |
| p981.scan.gate.identity | V04 | nearest-subject 상대귀속 |
| p981.scan.gate.face_present | V05 | 존재 게이트 (identity 탈뭉침 분리) |

## mdl — frozen model 자산 (불투명 키; 슬롯과 분리)

모듈 참조를 흔들지 않고 가중치를 교체하기 위한 층. **라이선스는 필드** — 상업화
게이트가 여기 걸린다. 형식: `mdl-<불투명4>`. 씨앗 등록(전수 등록은 후속 —
model-inventory 메모리가 원료):

```yaml
- {id: mdl-bffl, name: "buffalo_l (insightface)", binds: [M01, M02, V04], license: "비상업 연구 ⚠"}
- {id: mdl-mdpk, name: "MediaPipe FaceLandmarker", binds: [M01, M10], license: Apache-2.0}
- {id: mdl-segf, name: "jonathandinu/face-parsing", binds: [M09], license: CC BY-NC? 확인}
- {id: mdl-fcLp, name: "patrickjohncyh/fashion-clip", binds: [M09], license: MIT}
- {id: mdl-dino, name: "DINOv2", binds: [M05], license: Apache-2.0}
- {id: mdl-mica, name: "MICA (face_id→FLAME β)", binds: [], status: 후보, license: "MPI 비상업+학습금지 ⚠⚠"}
```

## p981.gen — MomentGen (경계 유동 → 불투명 키 예약)

세부 모듈 미분화 상태 — **지금이 불투명 키 도입 적기**(리네이밍 지옥 방지).
스타일 = `sty-<불투명2>` + name 필드; 상태는 필드로:

```yaml
- {id: sty-a1, name: "pfp",       subsystem: p981.gen, status: 구상, consumes: [p981.if.likeness]}
- {id: sty-b7, name: "photocard", subsystem: p981.gen, status: 구상, consumes: [p981.if.portrait]}
- {id: sty-c2, name: "fullbody",  subsystem: p981.gen, status: 구상, consumes: [p981.if.portrait]}
- {id: sty-d9, name: "orbit360",  subsystem: p981.gen, status: 구상, consumes: [p981.if.likeness]}
```

## dep — 종속 표기 (정본은 코드)

표기법: `dep: <출발> → <도착> [runtime|data, required|optional]`.
**scan 내부 dep은 이 문서에 손으로 복제하지 않는다**(드리프트 원천) — 정본 =
analyzers.py 선언, 렌더 = `momentscan map cascade`·`verify registry`. 이 문서가
드는 것은 **크로스-시스템 dep만**(위 p981.if 절 — gen·회사 앱은 if.*에만).

## C — momentscan 내부 계약 원장 (contracts.md 번호 유지)

C1(Job/Result=if.* 배송 transport) · C4(stash) · C7(좌표) · C9(preset 자리) ·
C11(=p981.if.likeness의 스키마 홈) · C12(visualstack 경계). 계약은 소유물이 아니라
심판 — 배정 단위 아님.

## rq — 연구 배정 경계 (v1 판정 승계, 배정 단위 = rq ID)

배정 가능 조건 3(v1): ①입출력이 계약 ②자기 판정기(R2가 공통 전제) ③자유/동결
명시. **배정 브리프의 ID = `p981.scan.rq.<leaf>`** (leaf는 mod와 동일 토큰 —
`p981.scan.rq.fashion` 브리프 = M09의 연구 위임).

| 등급 | 대상 (단축) | 비고 |
|---|---|---|
| 즉시 배정 | M05·M08·M09·M10·M11 · V01·V02·V03 · P1 | 계약+판정 자료 완비, 미결 질문 문서화 (M09 융합 τ·V01 darkness-blind·P1 캘리브레이션) |
| 조건부 | M02+V04(묶음 배정) · M12(P2/P3 조정 책임) · P2/P3(taste 라벨 선행) | 얽힘을 브리프에 명시 |
| 보류 | M01·M04(R16/R17 이관 대기) · M03(도메인 정책 얽힘) | 이관/정책 확정 후 |
| 배정 아님 | C-계약 전부 | 변경은 양쪽 합의 |

메커니즘: rq 브리프 1장 = 입출력(analyzers 선언)+판정 명령+자유/동결+미결 질문 +
**binds된 mdl의 라이선스 제약**. R16 isolation 실현 시 연구자별 환경 격리.

## 경계 밖 (ID 미부여, 필요 시 확장)

service/eureka(실행기 — C1이 커버), stash/telemetry(인프라), 인스펙터/리포트(표면),
../appearance-engine(자체 축 ID: G/C/H/A/S/W)·../hair — 단, appearance-engine의
face_recipe는 p981.if.likeness의 1차 소비자로 dep에 등장.

Enforcement 후보(미착수): `verify registry`가 단축코드↔정식ID↔코드 레지스트리
일치·유일성 체크. 지금은 문서가 정본.
