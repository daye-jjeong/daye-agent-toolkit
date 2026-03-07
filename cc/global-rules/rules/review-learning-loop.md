# Review Learning Loop

Simplify/PR Review에서 수정사항이 2개 이상 나오면, 반복 가능한 패턴을 auto memory에 기록하라.

## 기록 형식

auto memory `patterns.md`에 추가:
```
- [YYYY-MM-DD] {패턴}: {구현 시 해야 할 것}
```

## 기록 대상

- Schema enum 추가 시 → 모든 레이어(workspace 시그니처, CLI cast)에 타입 전파
- 헬퍼 함수 추출 시 → 직접 단위 테스트 함께 작성
- 필터/판단 로직 추가 시 → 3곳 이상 사용되면 헬퍼로 추출
- 기타 2회 이상 반복된 리뷰 지적 패턴

## 목적

같은 지적이 다음 세션에서 반복되지 않도록 한다.
