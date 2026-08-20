---
name: mabinogi-farming
description: 마비노기 모바일 영혼석 파밍 대시보드 — 어느 던전을 돌아야 시간당 데카(거래소 재화)로 이득인지, 재화(은동전·공물)/무료로 나눠 본다. 날짜별 드랍률·시간당 개수·판당 소요·매일 성과. "마비노기 파밍", "영혼석 어디서", "파밍 대시보드", "던전 효율" 요청에 사용.
---

## 무엇을 답하나

background-automator(자동화 앱)가 남긴 파밍 로그를 읽어 **"어느 던전이 시간당
데카로 이득인가"**에 답하는 로컬 웹 대시보드다. 데카는 거래소 재화이지 골드가
아니다 — 시간당 개수 × 거래소 시세로 환산한다.

| 보는 것 | 내용 |
|---|---|
| 던전 순위 | 시간당 데카 내림차순. 영혼석 5종 칩 필터, [전체/재화/무료] 토글 |
| 던전 상세(행 클릭) | 언제 돌렸나(세션)·날짜별 드랍률(패치 감지)·전리품·시간대 |
| 재화/무료 분리 | 순위·상세·활동량 전부 재화 판/무료 판을 갈라 본다 |
| 활동량 차트 | 날짜별 총 데카(재화/무료 stacked) + 시간당 데카 추세선 |
| 전체 데이터·교정 | 판마다 개별 수정, OCR 교정 사전 편집 |

데카는 **시세가 있어야** 나온다 — 시세는 [[mabinogi-equipment-cost]]가 거래소에서
모아 둔 저장소를 읽어 온다. equipment-cost를 한 번도 안 돌렸으면 데카 열이 비고
개수만 뜬다.

## 쓰는 법

```bash
python3 scripts/run.py                # 서버 뜨고 브라우저 열림(기본 8765)
python3 scripts/run.py --port 8804    # 포트 지정
python3 scripts/run.py --no-browser   # 브라우저 자동열기 끔
```

새로고침(F5)마다 로그·시세를 다시 읽는다 — 앱이 도는 중이면 최신 판까지 반영된다.

## 구조

이 스킬은 **얇은 진입점**이다. `scripts/run.py`가 레포 루트를 찾아 실제 프로그램을
실행한다. 코드 본체는 `apps/mabinogi/farming/`에 있다:

- `farming-dashboard.py` — 웹 서버·화면 (stdlib http.server, 인라인 SVG)
- `analyze-logs.py` — 집계 이음새(`soul_dungeon_ranking`·`dungeon_detail`·
  `daily_soul_deca`). 여기서 새로 세지 않는다 — 터미널·웹 숫자가 갈리지 않게
- `loot-corrections.json` — OCR 교정 사전(코드 밖 편집)
- `test_analyze_logs.py` — 집계 테스트

store 경로(파밍 로그·시세 DB)는 `apps/mabinogi/shared/mabi/data.py`가 한 곳에서
해석한다. 데이터 계약은 `apps/mabinogi/README.md`. 데이터는 `~/.mabi/`(git 밖).

## 데이터가 어디서 오나

```
background-automator(Swift 앱)  →  cycle-log.jsonl  →  이 대시보드
mabinogi-equipment-cost(시세)   →  prices.db        ↗  (데카 환산)
```

파밍 로그는 자동화 앱이 매 판 남긴다. 이 스킬은 **읽어서 분석**만 한다(개별 판
수정은 예외 — 원본을 다시 쓰며 `.jsonl.bak` 백업, 봇 멈추고 하길 권한다).
