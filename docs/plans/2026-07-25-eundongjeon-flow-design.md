# 은동전 분기 + 사이클 로깅 설계 (2026-07-25)

던전 파밍 자동화의 은동전(silver coin) 분기 처리 + 사이클별 전리품/시간 로깅 설계.
사용자와 실화면 캡처 기반으로 매핑한 결과.

## 배경
- 은동전 쓰고 들어간 던전은 클리어 후 "발견한 전리품"이 숨겨져 클릭 연출이 들어감 → 앱이 매칭 룰 없어 정지.
- 은동전 10+개면 입장 화면 동작이 달라짐(안내문 없음, "10 입장하기") → 기존 로직으로 정지.
- 사이클별 전리품/시간을 기록해 나중에 드랍률·소요시간 분석하고 싶음.

## 상태머신 (원천 순서 — 확정, S5만 재확인)
현재 구현은 stateless 프레임 매처지만, 확장 대비 순서를 원천 모델로 명시.
```
S1 일반 전투
S2 장면넘기기① (보스전 돌입 컷신)        → 빈공간 탭 (scene_skip)
S3 보스 전투
S4 화면터치 "화면을 터치해 주세요" (보스 클리어) → 빈공간 탭 (clear_touch)
S5 장면넘기기② (클리어 컷신) [로그엔 있음, 사용자 설명엔 없음 — 재확인 필요]
S6 발견전리품 (상자+던전명+전투시간+발견전리품 = 한 화면)
     · 코인 안 씀: 아이템 바로 보임
     · 코인 씀: "발견한 전리품" 숨김 → 클릭해 펼침   ★NEW 룰★
S7 재도전 메뉴 (나가기/다시하기/다음구역) → "다시하기" 클릭
S8 던전 선택 구간 (선택됨/도전/입장하기) — 은동전 사용 결정
     · 코인 <10: 다시하기→계속하기→여기, "선택을 해제하면…" 안내문 有 → 선택됨 해제 → 입장하기
     · 코인 ≥10: 다시하기→바로 여기, 안내문 無 → 옵션(소모ON=10입장하기 / OFF=선택됨해제)
   → 입장 → S1
```
분기 A(S6): 이번 런 코인 사용? / 분기 B(S8): 지금 코인 ≥10?

## 장면별 트리거 (기존 룰)
매 프레임: 캡처→OCR→룰의 requiredTexts 전부 있음 + forbidden 없음 + region/appearance 통과 → 안정화(2회) → targetText 박스 클릭(or safePoint 빈공간). 매칭 = `semanticText` 완전 일치(공백만 제거).

| 룰 | 트리거(required) | 가드 | 액션 | conf |
|---|---|---|---|---|
| scene_skip | "장면 넘기기" | — | 빈공간 | 0.4 |
| clear_touch | "화면을 터치해 주세요" | ¬장면넘기기 | 빈공간 | 0.85 |
| reward_retry | "다시 하기" | ¬장면넘기기 | "다시 하기" | 0.85 |
| continue_dialog | "계속하기" + "던전 탐험을 계속하시겠습니까?" | ¬장면넘기기 | "계속하기" | 0.45 |
| reward_detail ✅ | "발견한 전리품" | ¬장면넘기기 **+ ¬"다시 하기"** | "발견한 전리품"(글자) | 0.45 |
| mission_selection | "도전" | ¬장면넘기기 **+ 도전이 컬러(활성) appearance** | "도전" | 0.85 |
| deselect_challenge | "선택을 해제하면 임무 없이 입장할 수 있습니다." | ¬장면넘기기 | "선택됨" | 0.45 |
| enter_ready | "입장하기" | ¬장면넘기기 **+ ¬안내문** | "입장하기" | 0.45 |
| running | (센티넬, OCR 매칭 안 됨) | — | 없음 | 0.9 |

던전명 인식: reward_retry / mission_selection / enter_ready 화면에서. dungeonRuns=clear_touch 카운트, byDungeon=이름 인식분만.

## 알려진 문제 3개 + 수정
1. **발견전리품 정지**: 매칭 룰 없음 → 코인런 정지. **[P1a ✅ 구현 완료 — reward_detail]**
   → **신규 룰 reward_detail**(clear_touch와 reward_retry 사이 = S6): requiredText "발견한 전리품", targetText "발견한 전리품"(글자 클릭, safePoint 아님).
   → 패턴: `reward_retry`처럼 targetText 글자 클릭 + **정상 차단 룰**(forbiddenTexts에 "장면 넘기기"; scene_skip 예외 아님 — scene_skip은 차단의 유일한 예외라 반대 모델).
   → 배선: `AutomationScene.rewardDetail` case + `expectedRuleID`="reward_detail" + `sceneHasDungeonName`=true.
   → 실측(loot3.png 1512×949): "발견한 전리품" cf **0.50**(장식 폰트) → low-conf 룰(minimumOCRConfidence 0.45, region landscape 0.35–0.65 / 0.33–0.50). exact-match + forbidden으로 오탐 차단. 코인 안 쓴 런도 이 글자가 떠서 눌리지만 무변화(사용자 확인).
   → **"다시 하기" forbidden 필수**: 실측(코인 안 쓴 런 결과 화면)에 "발견한 전리품"(y0.46)과 "다시 하기"(y0.91)가 **동시에** 뜬다 → 룰 2개가 동시 후보 → `ambiguousObservation`으로 자동화 정지. 코인런(loot3)엔 재도전 메뉴가 없어 안 겹쳤다. 재도전 메뉴가 이미 떴으면 헤더를 안 누르고 "다시 하기"로 직행(목적지 동일).
2. **10+ 입장 정지**: 안내문 없어 deselect 안 뜸 + "입장하기" 완전일치라 "10 입장하기"(OCR `) 입장하기`) 안 맞아 enter 안 뜸 → 완전 정지.
   → **enter_ready "입장하기" 접미사 매칭** (`) 입장하기`/`10 입장하기` 끝이 "입장하기" → 매칭). 부작용 거의 없음.
3. **코인 있을 때 deselect 루프**: deselect(선택됨→도전 활성)→mission_selection 재선택→반복.
   → **은동전 소모 옵션**(설정 토글). ON=선택됨 유지하고 입장(루프 회피). OFF+코인=별도 처리.

## loot-log 설계 (사이클별 기록)
발견전리품 화면(S6)에서 던전명·전투시간·전리품을 한 번에 추출. 클릭 로그(activity-log, 클릭당)와 분리해 사이클당 1줄.

**파일**: `~/Library/Application Support/BackgroundAutomator/loot-log.jsonl`

**스키마**:
```json
{
  "at": "2026-07-25T04:16:12Z",
  "dungeon": "룬다 1층 2구역",
  "combatSeconds": 13,      // "순수 전투 시간 M:SS" 파싱 (순수 전투)
  "cycleSeconds": 62,       // 앱 실측 사이클 시간 (now - lastCycleAt, 텀 크면 null)
  "coinUsed": true,
  "items": [
    {"name":"골드","qty":1382,"guaranteed":true},
    {"name":"조각난 흑요석","qty":2,"guaranteed":false}
  ]
}
```

## activity-log 확장 (씬 타이밍 — 속도 최적화용)
씬 타이밍은 **사이클 레코드가 아니라 기존 activity-log(클릭당 이벤트) 확장**으로 남긴다.
이유: 최적화 분석은 "씬별 평균/p95" 집계라 per-event **flat 로그**가 유리(사이클 nesting은 unnest 필요).

**원천은 시점(timestamp), 소요는 시점 차로 계산.** (소요만 남기면 "언제"가 소실 → 세션 윈도우 불가)

기존: `{at, outcome, scene, dungeonName}`
확장 (페이즈 전이 시점 추가):
```json
{"at":"…클릭완료", "outcome":"clicked", "scene":"reward_retry", "dungeonName":"…",
 "sceneAt":"…씬 첫 감지", "idleAt":"…유휴 대기 시작", "clickAt":"…클릭 실행 시작"}
```
- observe(관찰) = idleAt − sceneAt
- idle+재관찰 = clickAt − idleAt
- click = at − clickAt / total = at − sceneAt
→ "어느 씬/버튼이 느린지" 짚어 최적화. (앞선 실측: 버튼당 ~4초 = 관찰~2 + 유휴/재관찰~1.5 + 클릭~0.7 → 재관찰 조건부 생략이 줄일 여지.) 편의상 ms 병기 가능하나 원천은 시점.

## 세션 경계 로깅 (전체 디버깅용)
파밍 생명주기 이벤트를 시점과 함께 로그 → "언제부터 언제까지 돌렸나 + 몇 번 끊겼나".
```json
{"at":"…","event":"session_start"}
{"at":"…","event":"session_stop","reason":"user"}
{"at":"…","event":"paused","reason":"복원 실패: 원래 앱 최전면 복귀 실패"}
{"at":"…","event":"resumed"}
```
restorationFailed 로깅(이미 추가됨)과 같은 패턴 확장. activity-log에 특수 event로 넣거나 별도 session-log.

**정리**: loot-log = 사이클별(전리품/전투시간/사이클시간/드랍). activity-log = 클릭별(씬 페이즈 시점/속도) + 세션 경계 이벤트. 전부 `at`(시점) 기준, `dungeon`으로 조인.

## 분석 목표 (나중 — 차트 대시보드)
로깅은 아래 분석을 지원해야 함(현 스키마가 충족):
| 차트 | 출처 |
|---|---|
| 세션 구간(몇시~몇시) + 총 런타임 | 세션 이벤트(start/stop/pause) 시점 |
| 사이클 수(몇 바퀴) | loot-log 레코드 수 |
| 얻은 전리품(누적/종류) | loot-log `items` 집계 |
| 던전별 비교(시간·드랍·속도) | loot-log / activity-log `dungeon` group by |
| 씬별 속도 병목 | activity-log 페이즈 시점 |
| 필드 | 출처 |
|---|---|
| dungeon | 기존 DungeonNameExtractor |
| combatSeconds | "순수 전투 시간 M:SS" 정규식 |
| cycleSeconds | 앱이 lastCycleAt 기억 → now-lastCycleAt (일시정지/중단 텀이면 null) |
| coinUsed | 발견전리품 숨김+클릭연출 여부 / 코인 개수 변화 |
| items | 아이템 그리드 OCR — 이름 박스 + 수량 박스 위치 페어링 |
| guaranteed | 아이콘 위 "확정" 라벨 유무 |

분석(나중): 드랍률 = 아이템 등장수/총 사이클, 던전별 평균 순수/실제 시간, 시간당 기대 드랍.

## 구현 페이즈
1. **[P1a ✅ 완료] 발견전리품 룰(reward_detail)** — "발견한 전리품" 글자 클릭. 코인런 정지 해소. TDD(310 tests green, warnings-as-errors clean).
2. **[P1b] loot-log** — S6에서 던전명/전투시간/사이클시간/전리품 추출·기록. 발견전리품 룰과 같은 화면. 아이템 OCR 신뢰도 스파이크 먼저.
3. **[P2] enter_ready 접미사 매칭** — 10+ 입장 해소.
4. **[P2] 은동전 소모 옵션** — 설정 토글 + 코인 루프 회피.

## 열린 항목
- S5(장면넘기기②) 성격 재확인.
- **loot-log 던전명(P1b)**: 발견전리품 화면 던전명은 cf 0.50 < DungeonNameExtractor 임계 0.9 → 안 뽑힘. 이 씬만 임계 낮추거나 reward_retry/enter_ready 씬 던전명 사용.
- coinUsed 판정 방법 확정.
- 아이템 이름↔수량 위치 페어링 로직 + 수량 OCR 신뢰도.
- 확정 vs 확률 드랍 구분(확정 라벨 OCR).

## 캡처 참조 (scratchpad, 세션 한정)
loot3.png=발견전리품 / silver10-selected.png=10+입장(안내문 없음) / silver-available.png=10+입장 초기 / exit-retry-next.png=전투복귀.
