# Register 토픽 분류

교정 사항을 주제별로 분류하여 `corrections/{topic}.md`에 저장한다.

## 기본 토픽

| 토픽 | 파일명 | 포함 내용 |
|------|--------|----------|
| 도구/런타임 | `tooling.md` | 패키지 매니저, CLI, 빌드 도구, 런타임 설정 |
| 아키텍처 | `architecture.md` | 디자인 패턴, 파일 구조, 모듈 구성 |
| 테스팅 | `testing.md` | 테스트 프레임워크, 테스트 작성 규칙, 커버리지 |
| 코딩 스타일 | `style.md` | 네이밍, 포매팅, 언어별 관습, 코드 구조 |
| API/외부 연동 | `integrations.md` | API 사용법, 인증, 외부 서비스 연동 |
| 일반 | `general.md` | 위 카테고리에 속하지 않는 교정 |

## 토픽 자동 분류 규칙

키워드 기반으로 자동 분류:
- npm, bun, node, python, docker, CLI → `tooling.md`
- pattern, structure, module, layer, DI → `architecture.md`
- test, jest, vitest, mock, assert → `testing.md`
- name, format, lint, prettier, indent → `style.md`
- API, auth, fetch, endpoint, webhook → `integrations.md`
- 그 외 → `general.md`

## 새 토픽 생성

기존 토픽에 맞지 않는 교정이 3개 이상 `general.md`에 쌓이면:
1. 공통 주제를 식별
2. 새 토픽 파일 생성을 사용자에게 제안
3. 승인 시 해당 항목을 새 토픽으로 이동
