# Memory Lifecycle

## project 메모리 금지
`type: project` 생성 금지. 프로젝트 상태는 코드/커밋/docs에 남긴다. 허용: `feedback`/`user`/`reference`만.

## 정리
기존 project 메모리는 작업 완료 시 삭제(파일 + MEMORY.md 인덱스). 후속 작업 명시된 건 유지.
Why: 누적되면 시스템 프롬프트 비대.

## 승격 후 삭제
feedback memory 내용을 룰·SKILL.md·CLAUDE.md로 옮겼으면 memory 파일을 지운다(+ 인덱스). 둘 다 자동 로드라 남겨두면 매 세션 같은 내용이 두 번 들어간다.
