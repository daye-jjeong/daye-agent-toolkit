# 완료 검증과 커밋

## 완료 전 검증

"done" 주장 전에 반드시 실행하라:
1. 관련 테스트 실행 + 통과 확인
2. `tsc --noEmit` (TypeScript 프로젝트)
3. Cross-file 일관성 체크 (참조, 스케줄, 플래그명)

Why: 검증 없는 완료 주장은 broken tests, type errors, cross-file 불일치를 숨긴다.
완료라고 생각한 후에도 한 번 더 검증하라.
