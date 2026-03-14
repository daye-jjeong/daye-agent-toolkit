---
name: self-profile
description: 업무 데이터 기반 자기 프로파일링 — 정량 분석 + 페르소나 생성
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Self-Profile Skill

**Version:** 0.1.0 | **Updated:** 2026-03-14

업무 데이터를 종합 분석하여 "나는 어떤 사람인가"를 정량 + 서술형으로 프로파일링한다.
life-coach(단기 코칭)와 분리된 **장기 자기 인식** 도구.

## 프로파일 생성/갱신 (/self-profile)

### Step 1. 데이터 수집

```bash
# 기본 (최근 30일)
python3 {baseDir}/scripts/collect.py

# 기간 지정
python3 {baseDir}/scripts/collect.py --days 60
python3 {baseDir}/scripts/collect.py --since 2026-02-01

# 특정 프로젝트만 교정 이력 스캔
python3 {baseDir}/scripts/collect.py --project-roots /path/to/project1,/path/to/project2
```

출력: JSON (stdout + `~/life-dashboard/profile-snapshot.json` 저장)
이전 snapshot은 `profile-snapshot.prev.json`으로 자동 백업.

### Step 2. 기존 데이터 확인

다음 파일이 존재하면 Read:
- `~/life-dashboard/profile.md` — 이전 프로파일
- `~/life-dashboard/profile-snapshot.prev.json` — 이전 snapshot (변화 비교용)

첫 실행이면 건너뛴다.

### Step 3. 분석 + 프로파일 작성

`references/profile-dimensions.md`의 7개 차원 프레임으로 데이터를 분석한다.

**당신은 분석가다.** 숫자를 나열하지 마라 — 패턴을 읽고, 해석하고, 인사이트를 도출해라.

**프로파일 구성:**

```markdown
# 다예 업무 프로파일
> 생성: YYYY-MM-DD | 분석 기간: YYYY-MM-DD ~ YYYY-MM-DD

## 정량 요약
(핵심 수치: 세션 수, 평균 길이, 집중 시간대, 태그 비율, 소스 비율)

## 페르소나
(데이터 기반 서술형 인물 묘사 — 200자 내외, 핵심 특성 3-4가지)

## 강점
(데이터가 뒷받침하는 강점 — 각각 근거 수치 포함)

## 개선 포인트
(각 항목: 근거 → 현재 방식 → 제안 방식 → 적용 방법)

## 변화 추이
(이전 snapshot 대비 ±10% 이상 변화, 개선/악화 감지)
```

### Step 4. 저장 + 차트

1. 프로파일을 `~/life-dashboard/profile.md`에 Write
2. 차트 생성 (matplotlib):
   - 태그 비율 파이차트
   - 시간대별 활동 히트맵
   - 일별 추이 라인차트
   - 폰트: `Apple SD Gothic Neo`, 배경: `#1C1C1E`
   - `/tmp/self_profile_charts.png`에 저장 후 `open`

## 참조

| 파일 | 내용 |
|------|------|
| `references/profile-dimensions.md` | 7개 분석 차원 상세 + 해석 기준 |
| `scripts/collect.py` | DB → JSON 데이터 수집 |
