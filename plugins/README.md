# plugins/ — 격리된 모델 백엔드 (스테이지 노드가 아님)

여기 패키지들은 **선택적 확장이 아니라 필수 백엔드**다. 스테이지 *노드*는 전부
`apps/momentscan/src/momentscan/extraction/`에 있고(`ls extraction/` = DAG 어휘 전체),
이 디렉토리는 그중 features/scene 노드가 호출하는 **모델-무거운 절반**을 격리한다 —
visualstack의 plugins가 detect/landmarks 뒤에 있는 것과 같은 관계.

격리의 이유 (아키텍처 계층이 아니라 이음매):
1. **의존성** — 무겁고 충돌 가능한 모델 스택(onnx·torch·transformers)을 코어와 분리
2. **FeatureSource 스왑 포트** — `momentscan.ports.FeatureSource` 계약 뒤에서 교체 가능
3. **서비스 워커 경계** — 연동 시 추출 워커를 별도 배포 단위로 뗄 수 있는 자리

| 패키지 | 상태 | 내용 |
|---|---|---|
| `features-specialist45d` | **가동 중** | 46-dim 추출(HSEmotion·AU·DPR-SH) + DINO scene + registry 계약(INDEX) — 앱 6개 모듈이 소비 |
| `features-vjepa` | 예약석 (Phase 4, 소비자 0) | 원래 two-track 설계의 Track B(V-JEPA) 스텁 — jepa-poc.md, 보류 연구 |
