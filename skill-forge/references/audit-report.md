# 감사 리포트 포맷 및 기준

## 구조 점검 리포트 포맷

```
=== Skill Audit Report ===

| 스킬 | SKILL.md | refs/ | .claude-skill | 상태 |
|------|----------|-------|---------------|------|
| mermaid-diagrams | 217줄 | 7개 | O | W 최적화 권장 |
| skill-forge | 98줄 | 3개 | O | V 양호 |
| notion | 85줄 | 0개 | X | V 양호 (OC전용) |

권장 사항:
- mermaid-diagrams: 217줄 -> 최적화 필요 (타겟: 150줄)
```

## 상태 기준

| 상태 | 기준 |
|------|------|
| V 양호 | 150줄 이내 + 해당 분류에 맞는 메타파일 존재 |
| W 최적화 권장 | 150줄 초과 |
| X 구조 문제 | frontmatter 미비 또는 필수 파일 누락 |

## 드리프트 분석 리포트 포맷

```
=== Drift Analysis ===

변경된 파일: 12개 (git diff main...HEAD)

| 변경 파일 | 영향받는 스킬 | 드리프트 유형 |
|-----------|--------------|--------------|
| scripts/health/track.py | health-tracker | 참조 파일 수정 |
| skills/new-skill/SKILL.md | (신규) | 매니페스트 미등록 |
| .claude/rules/corrections.md | correction-memory | 교정 규칙 변경 |

액션 필요:
- health-tracker: scripts/health/track.py 변경 확인 필요
- new-skill: skills.json 및 CLAUDE.md 등록 필요
- correction-memory: corrections.md 변경이 교정 규칙에 영향 확인 필요

변경 무관 스킬: 25개 (영향 없음)
```

## 드리프트 유형

| 유형 | 설명 | 자동 수정 가능 |
|------|------|---------------|
| 참조 파일 수정 | 스킬이 참조하는 파일이 변경됨 | X (수동 확인) |
| 참조 파일 삭제 | 스킬이 참조하는 파일이 삭제됨 | X (수동 확인) |
| 매니페스트 미등록 | 새 스킬이 skills.json/CLAUDE.md에 없음 | O |
| 패턴 불일치 | 스킬의 패턴/값이 코드 변경과 불일치 | X (수동 확인) |
