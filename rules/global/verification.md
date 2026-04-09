# Done Verification

"done" 주장 전 필수:
1. 관련 테스트 실행 + 통과
2. `tsc --noEmit` (TypeScript 프로젝트)
3. Cross-file 일관성 (참조, 스케줄, 플래그명, 분산 문서)

검증 없는 완료 주장은 broken tests, type errors, cross-file 불일치를 숨긴다.
