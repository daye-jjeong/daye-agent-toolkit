# Context Rot 방지

## CLAUDE.md 크기
CLAUDE.md + 로드되는 rules 합계가 3,000 토큰(한글 ~1,500자)을 넘으면 다이어트 제안하라.
세션 시작 시 확인하지 마라. 세션 중 CLAUDE.md를 수정할 때만 체크.

## /compact 타이밍
구현 중 compact 금지 — 변수명, 파일 경로, 부분 상태를 잃는다.
마일스톤 전환 시(리서치→구현, 디버깅→다음 기능) compact 제안.

## MCP 서버
프로젝트당 MCP 10개 이하. 도구 설명이 매 턴 토큰을 먹는다.
안 쓰는 MCP는 disabled: true.
