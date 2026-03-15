# plan 작성 후 Codex 리뷰 완료 전 구현 착수 금지

writing-plans로 plan을 생성한 뒤, codex-cli exec 모드로 plan 리뷰를 완료하기 전까지 구현 단계로 넘어가지 마라.

Why: 감사 결과 Codex plan 리뷰 준수율 0% (5건 중 0건). 규칙이 존재하지만 한 번도 실행된 적 없는 사문화 상태. subagent-driven-development, executing-plans 등 구현 스킬 호출이 리뷰 없이 진행됨.

금지 대상: `subagent-driven-development`, `executing-plans` 스킬 호출, 또는 plan 태스크의 직접 구현 착수.
