# Memory Lifecycle

## project 메모리 금지
`type: project` 생성 금지. 프로젝트 상태는 코드/커밋/docs/에 남긴다.
허용 타입: `feedback`, `user`, `reference`만.

## project 메모리 정리
기존 project 메모리는 작업 완료 시 삭제 (master 머지 + 후속 없음).
삭제: 파일 + MEMORY.md 인덱스.

Why: project 메모리 누적 → 시스템 프롬프트 비대.

예외: 후속 작업 명시된 건 유지. feedback/user/reference는 대상 아님.
