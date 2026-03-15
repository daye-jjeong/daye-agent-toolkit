# brainstorming 후 spec 완료 전 writing-plans 호출 금지

brainstorming 체크리스트 6-8(spec 작성, spec review loop, 사용자 리뷰)을 모두 완료한 뒤에만 writing-plans를 호출하라.

Why: 감사 결과 spec review loop 준수율 0%. "디자인 합의했으니 바로 plan 쓰자"로 리뷰 게이트를 통째로 건너뛰는 패턴이 반복됨.

확인 방법: `docs/superpowers/specs/` 경로에 해당 spec 커밋이 존재하는지 확인.
