# vault-memory:meeting-note

> 미팅 트랜스크립트를 결정/액션아이템/논의로 구조화한다.

**기록 규격**: `vault/format.md` 참조

## 트리거

- "미팅 정리", "meeting note", "회의록", "미팅 노트"
- 트랜스크립트 붙여넣기 시

## 워크플로우

### 1. 입력

사용자가 제공:
- 미팅 트랜스크립트 (텍스트) 또는 구두 요약
- 메타데이터: 제목, 날짜, 참석자 (자동 감지 시도)

### 2. 프로젝트 감지

키워드로 `vault/projects/` 하위 프로젝트명과 매칭.
매칭 없으면 사용자에게 지정 요청.

### 3. 구조화

```markdown
---
date: YYYY-MM-DD
type: meeting
title: "미팅 제목"
attendees: [이름1, 이름2]
project: project-code
updated_by: claude-code
updated_at: ISO-8601
tags: [meeting, project-code]
---

## 요약
1-3줄 핵심 요약

## 결정사항
- **[결정1]**: 설명 (담당: @이름)

## 액션 아이템
- [ ] 할 일 — @담당자, 기한: MM/DD

## 논의 내용
### 주제 1
- 포인트
```

### 4. 저장

**경로**: `vault/reports/meeting-YYYY-MM-DD-{slug}.md`
- slug: 미팅 제목에서 생성 (예: `meeting-2026-02-11-vault-design`)

### 5. 후속 제안

- 액션 아이템 → 태스크 생성 제안
- 관련 프로젝트 `_project.md`에 미팅 참조 링크 추가 제안
