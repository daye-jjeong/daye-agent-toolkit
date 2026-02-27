---
name: correction-memory
description: 교정 기억 — 실수를 3계층으로 기록하여 반복 방지
argument-hint: "save" 또는 "search <키워드>" 또는 "review" 또는 "stats"
---

# Correction Memory

교정 사항을 3계층(Rules → Register → Log)에 동시 저장하여,
같은 실수를 반복하지 않게 한다. Boris Cherny의 "Compounding Engineering" 패턴 기반.

## 모드 판단

$ARGUMENTS를 파싱하여 모드 결정:

| 키워드 | 모드 | 설명 |
|--------|------|------|
| `save`, `기억해`, `저장` | **저장** | 교정 사항을 3계층에 동시 저장 |
| `search`, `검색`, `찾아` | **검색** | 키워드로 교정 이력 검색 |
| `review`, `정리`, `리뷰` | **리뷰** | 현재 규칙 전체 리뷰 + 중복/모순 제거 |
| `stats`, `통계` | **통계** | 주제별 빈도, 최근 추세 |

키워드 없으면 `save` 모드로 동작.

## 3계층 아키텍처

| 계층 | 경로 | 공유 | 용도 |
|------|------|------|------|
| **Rules** | `{project}/.claude/rules/correction-{slug}.md` | git (팀) | Claude에게 적용할 행동 규칙 (파일 1개 = 규칙 1개) |
| **Register** | auto memory `corrections/{topic}.md` | 로컬 (나만) | 주제별 교정 이력 + 사유 |
| **Log** | auto memory `corrections/log/YYYY-MM-DD.md` | 로컬 (나만) | 교정 발생 타임라인 |

> auto memory 경로: `~/.claude/projects/{project-hash}/memory/corrections/`

## 모드별 상세

### 저장 (save)

교정 전파 프로토콜: [correction-propagation.md](references/correction-propagation.md)

### 검색 (search)

1. $ARGUMENTS에서 키워드 추출
2. Layer 1 (Rules) 검색 → 현재 적용 중인 관련 규칙
3. Layer 2 (Register) 검색 → 주제별 교정 이력
4. 결과를 구조적으로 보여주기

### 리뷰 (review)

자동 트리거: save 시 규칙이 50개 이상이면 review 제안.
수동 트리거: `/correction-memory review`

1. Layer 1 (Rules) `corrections.md` 전체 읽기
2. 중복 규칙 식별 + 병합 제안
3. 모순 규칙 식별 + 해결 제안
4. 더 이상 유효하지 않은 규칙 제거 제안
5. 사용자 승인 후 업데이트

### 통계 (stats)

1. Layer 3 (Log) 전체 파싱
2. 주제별 교정 빈도 집계
3. 최근 7일/30일 추세
4. 가장 많이 교정되는 토픽 → "집중 개선 필요" 안내

## 자동 트리거

교정 감지 → 자동 저장은 `.claude/rules/correction-protocol.md`가 담당.
이 규칙 파일은 매 세션 자동 로드되므로, 스킬을 명시적으로 호출하지 않아도 동작한다.
스킬의 search/review/stats 모드는 수동 호출용.

## Write Gate

저장 가치 판단 기준: [write-gate.md](references/write-gate.md)

## Register 토픽

초기 토픽 분류: [register-topics.md](references/register-topics.md)
