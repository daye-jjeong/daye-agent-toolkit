# life-coach HTML 리포트 전환

**날짜:** 2026-03-10
**상태:** 완료
**브랜치:** wt/life-coach-html

---

## 배경

일일/주간 코칭 리포트를 텍스트(텔레그램) 대신 HTML로 생성해서 로컬에서 열어보는 방식으로 전환.
타임라인 차트도 HTML 인터랙티브 뷰로 통합.

---

## 오늘 완료한 것

### timeline_html.py 신규 생성
- `shared/life-coach/scripts/timeline_html.py`
- 일일/주간 모두 지원 (`--weekly` 플래그)
- **인터랙티브 기능:**
  - 요일별 접기/펼치기 (▶ 클릭)
  - [레포별] [태그별] 토글 — 펼쳤을 때 그룹핑 축 전환
  - 막대 hover → 툴팁 (repo, tag, 시간, 요약)
  - 접힌 상태에서도 미니 타임라인으로 세션 분포 표시
- 사용법:
  ```bash
  python3 weekly_coach.py --json | python3 timeline_html.py --weekly
  python3 daily_coach.py  --json | python3 timeline_html.py
  open /tmp/work_timeline.html
  ```

### timeline_chart.py 신규 생성
- PNG 차트 생성 (matplotlib, Apple SD Gothic Neo 폰트)
- 일일: 세션별 가로 막대, X축 00:00~24:00
- 주간: 레포 기준으로 묶어서 하루 = 섹션, legend 포함
- 사용법:
  ```bash
  python3 daily_coach.py  --json | python3 timeline_chart.py
  python3 weekly_coach.py --json | python3 timeline_chart.py --weekly
  open /tmp/work_timeline.png
  ```

### weekly_coach.py 수정
- `--json` 출력에 `daily[].activities` 필드 추가 (일별 세션 상세)
- 타임라인 차트/HTML 생성에 필요한 데이터

### SKILL.md 업데이트
- 일일/주간 코칭 워크플로우에 차트 + HTML 생성 스텝 추가

---

## 남은 작업

### [x] 1. 일일 HTML 리포트 생성 (`daily_report.py` 신규)

현재 `daily_coach.py`는 텔레그램 텍스트만 생성함.
HTML 버전에서 보여줄 내용:

```
┌─────────────────────────────────────────────────┐
│  3/10(화) 데일리 리포트                           │
│  6세션 · 6.8h · 248M tokens                      │
├─────────────────────────────────────────────────┤
│  [타임라인 차트 — timeline_html.py 결과 인라인]   │
├─────────────────────────────────────────────────┤
│  📝 오늘의 정리   (LLM 코칭 텍스트)              │
│  🔍 코칭                                         │
│  🤖 자동화 제안                                  │
│  ⏭️ 내일 이어할 것                               │
├─────────────────────────────────────────────────┤
│  💊 건강 / 🧊 유통기한                           │
└─────────────────────────────────────────────────┘
```

구현 방식:
- `daily_coach.py --json` 으로 데이터 수집
- `timeline_html.py`에 `timeline_section_html(data, weekly=False) -> str` 함수 추출
  - 현재 `HTML` 상수 전체를 import하면 지저분함 → 타임라인 `<div>` 부분만 반환하는 함수로 분리
- `daily_report.py`가 해당 함수를 import해서 전체 HTML에 인라인으로 삽입
- LLM 코칭 텍스트는 CC 세션에서 직접 생성 후 HTML에 삽입 (스크립트가 생성하지 않음)

### [x] 2. 주간 HTML 리포트 생성

```
┌─────────────────────────────────────────────────┐
│  3/2 ~ 3/8 주간 리포트                           │
│  N세션 · Xh · YM tokens                         │
├─────────────────────────────────────────────────┤
│  [타임라인 — 요일별 접기/펼치기]                  │
├─────────────────────────────────────────────────┤
│  📝 주간 정리                                    │
│  🔍 방향성 코칭                                  │
│  🔮 다음 주 생각해볼 것                          │
└─────────────────────────────────────────────────┘
```

### [x] 3. SKILL.md 업데이트

일일/주간 코칭 워크플로우에 HTML 리포트 생성 스텝 반영:
```
# 일일 코칭
4. python3 scripts/timeline_html.py  → /tmp/work_timeline.html
5. (LLM이 코칭 텍스트 생성 후 HTML에 포함)
6. open /tmp/daily_report.html
```

---

## 파일 구조 (현재 + 예정)

```
shared/life-coach/scripts/
├── daily_coach.py       ← 데이터 수집 (수정 최소화)
├── weekly_coach.py      ← 데이터 수집 (activities 필드 추가 완료)
├── timeline_chart.py    ← PNG 차트 (완료)
├── timeline_html.py     ← 인터랙티브 타임라인 HTML (완료)
├── daily_report.py      ← [ ] 일일 HTML 리포트 (신규)
└── weekly_report.py     ← [ ] 주간 HTML 리포트 (신규)
```

---

## 설계 결정

- **LLM 코칭 텍스트**: 스크립트가 생성하지 않음. CC 세션의 LLM이 직접 생성한 후 HTML 템플릿에 삽입.
- **타임라인은 timeline_html.py 재사용**: `build()` 함수를 import해서 쓰거나, 인라인으로 삽입.
- **저장 경로**: `/tmp/daily_report.html`, `/tmp/weekly_report.html`
- **스타일**: timeline_html.py와 동일한 다크 테마 유지.

---

## 참고

- `shared/life-coach/SKILL.md` — 코칭 워크플로우 전체
- `shared/life-coach/references/coaching-prompts.md` — LLM 코칭 프레임
- `shared/life-coach/scripts/timeline_html.py` — 타임라인 HTML (재사용 대상)
