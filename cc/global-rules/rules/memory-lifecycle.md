# Memory Lifecycle

## project 타입 메모리 생성 금지

`type: project` 메모리 파일을 생성하지 마라. 프로젝트 상태는 코드, 커밋, docs/에 남긴다.
기록할 만한 설계 판단이 있으면 `docs/` 디렉토리에 문서로 작성하라 — memory가 아니다.

허용하는 메모리 타입: `feedback`, `user`, `reference`만.

## project 타입 메모리 정리

기존 `type: project` 메모리는 작업이 완료되면 삭제하라.

완료 판단 기준:
- 코드가 master에 머지됨
- "완료", "해결됨" 등 상태가 명시됨
- 후속 작업이 없거나, 남은 건 외부 의존(upstream issue 등)뿐

삭제 시:
1. 메모리 파일 삭제
2. MEMORY.md 인덱스에서 해당 항목 제거

Why: project 메모리가 누적되면 시스템 프롬프트가 비대해져 토큰 소비가 증가한다. 완료된 정보는 코드와 git history에 이미 존재한다.

## 예외

- 후속 작업이 명시된 project 메모리는 유지 (후속 완료 시 삭제)
- feedback/user/reference 타입은 이 규칙 대상 아님
