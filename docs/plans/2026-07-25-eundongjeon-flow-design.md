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

| 룰 | 트리거(required) | 가드(forbidden) | 액션 | conf |
|---|---|---|---|---|
| scene_skip | "장면 넘기기" | — | 빈공간 | 0.40 |
| clear_touch | "화면을 터치해 주세요" | ¬장면넘기기 | 빈공간 | 0.45 |
| reward_detail | "발견한 전리품" | ¬장면넘기기 ¬다시하기 ¬계속하기 | "발견한 전리품"(글자) | 0.45 |
| reward_retry | "다시 하기" | ¬장면넘기기 | "다시 하기" | 0.45 |
| continue_dialog | "계속하기" + "던전 탐험을 계속하시겠습니까?" | ¬장면넘기기 | "계속하기" | 0.45 |
| turn_off_double_loot | "도전에 성공하면…두 배가 됩니다." | ¬장면넘기기 | 그 문장 **아래**의 "선택됨" | 0.45 |
| deselect_challenge | "선택을 해제하면 임무 없이…" | ¬장면넘기기 | "선택됨" | 0.45 |
| deselect_double_loot ᴼᶠᶠ | "도전에 성공하면…" + "선택됨" | ¬장면넘기기 | "선택됨" | 0.45 |
| enter_with_coin ᴼᴺ | "도전에 성공하면…" + "선택됨" | ¬장면넘기기 | 끝말 "입장하기" | 0.25 |
| enter_ready | "입장하기" | ¬장면넘기기 ¬안내문 **¬선택됨** | "입장하기" | 0.45 |
| running | (센티넬, 매칭 안 됨) | — | 없음 | 0.90 |

ᴼᶠᶠ/ᴼᴺ = 은동전 옵션에 따라 하나만 로드된다(`RuleLoader.applyingSilverCoinChoice`).
`turn_off_double_loot`는 옵션과 무관하게 항상 로드된다 — 더블 루팅은 미지원이라 무조건 끈다.
`mission_selection`("도전")은 2026-07-26 제거. 아래 갱신 절 참조.

던전명 인식: reward_retry / enter_ready / reward_detail / enter_with_coin 화면에서.
dungeonRuns=clear_touch 카운트, byDungeon=이름 인식분만(이름은 글자·숫자만 남겨 정규화).

## 알려진 문제 3개 + 수정
1. **발견전리품 정지**: 매칭 룰 없음 → 코인런 정지. **[P1a ✅ 구현 완료 — reward_detail]**
   → **신규 룰 reward_detail**(clear_touch와 reward_retry 사이 = S6): requiredText "발견한 전리품", targetText "발견한 전리품"(글자 클릭, safePoint 아님).
   → 패턴: `reward_retry`처럼 targetText 글자 클릭 + **정상 차단 룰**(forbiddenTexts에 "장면 넘기기"; scene_skip 예외 아님 — scene_skip은 차단의 유일한 예외라 반대 모델).
   → 배선: `AutomationScene.rewardDetail` case + `expectedRuleID`="reward_detail" + `sceneHasDungeonName`=true.
   → 실측(loot3.png 1512×949): "발견한 전리품" cf **0.50**(장식 폰트) → low-conf 룰(minimumOCRConfidence 0.45, region landscape 0.35–0.65 / 0.33–0.50). exact-match + forbidden으로 오탐 차단. 코인 안 쓴 런도 이 글자가 떠서 눌리지만 무변화(사용자 확인).
   → **"다시 하기" forbidden 필수**: 실측(코인 안 쓴 런 결과 화면)에 "발견한 전리품"(y0.46)과 "다시 하기"(y0.91)가 **동시에** 뜬다 → 룰 2개가 동시 후보 → `ambiguousObservation`으로 자동화 정지. 코인런(loot3)엔 재도전 메뉴가 없어 안 겹쳤다. 재도전 메뉴가 이미 떴으면 헤더를 안 누르고 "다시 하기"로 직행(목적지 동일).
2. ~~**10+ 입장 정지**~~ **[오판정 — 실측으로 철회]**
   실측(2026-07-25, 은동전 **7개** 보유 = 10 미만인데도 `10 입장하기`가 뜸)으로 "10 = 보유량"이라는 전제가 틀렸음이 확인됐다. **"10"은 임무 전리품 2배에 드는 은동전 비용**이고, 버튼 글자는 **코인 잔량이 아니라 임무 선택 상태**를 따른다:
   | 상태 | 안내문 | 뱃지 | 입장 버튼 |
   |---|---|---|---|
   | 선택됨 | 有 | 선택됨 | `10 입장하기` |
   | 해제됨 | 無 | 도전 | `입장하기` |
   → 즉 기존 흐름이 정상 동작한다: 안내문 → `deselect_challenge`가 `선택됨` 클릭 → 해제되면 버튼이 `입장하기`가 되어 `enter_ready` 발동. **접미사 매칭 불필요**(오히려 선택 상태에서 잘못 눌러 은동전을 소모할 위험). 골든 테스트 `entryButtonTextDependsOnMissionSelectionNotCoinBalance`로 고정.
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

## 실측 캡처 인덱스 (Tests/Fixtures — 골든 테스트용, 커밋됨)
2026-07-25 라이브 캡처. 모두 1512×949, 은동전 7개(=10 미만) 계정.

| fixture | 장면 | 발동 룰 |
|---|---|---|
| landscape-scene-skip-boss-intro | S2 보스전 돌입 컷신(`장면 넘기기`+보스명) | scene_skip |
| landscape-scene-skip-clear | S5 클리어 컷신(`장면 넘기기` 단독) | scene_skip |
| landscape-clear-touch-live | S4 등급 화면(하단 `화면을 터치해 주세요` cf 1.0) | clear_touch |
| landscape-result-early | S6 결과 초기(전리품 채워지기 전) | reward_detail |
| landscape-reward-detail | S6 결과+전리품(**은동전 쓴 런**) | reward_detail |
| landscape-reward-detail-nocoin | S6 결과+전리품+재도전 메뉴(안 쓴 런) | reward_retry |
| landscape-loot-soulstone-nocoin | S6 **공명의 영혼석** 드랍 | reward_retry |
| landscape-continue-dialog-nocoin | S7 계속하기 팝업(전리품 헤더가 뒤에 남음) | continue_dialog |
| landscape-selected-nocoin | S8 임무 선택됨(안내문+`10 입장하기`) | deselect_challenge |
| landscape-deselected-nocoin | S8 해제됨(`도전`+`입장하기`) | enter_ready |
| landscape-mission-select-10coin | S8 은동전 10, 임무 선택됨(안내문 無) | deselect_double_loot |
| landscape-deselected-10coin | S8 은동전 10, 해제됨 | enter_ready |
| landscape-retry-menu-10coin | S7 재도전 메뉴(은동전 10) | reward_retry |
| landscape-loot-coin-used / -revealed | S6 코인런 결과(접힘/펼침) | reward_detail |
| landscape-autostart-gauge | 던전 입장 직후 자동시작 게이지 | (규칙 없음 — 아래 참조) |
| **landscape-double-loot-nomission** | S8 둘 다 해제, `총 탐험 전리품`, 🪙0 | enter_ready |
| **landscape-double-loot-available-off** | S8 임무만, 더블루팅 `도전` 활성, 🪙10 | deselect_double_loot |
| **landscape-double-loot-selected** | S8 둘 다 `선택됨`, 🪙20 | turn_off_double_loot |
| **landscape-loot-double-collapsed** | S6 더블루팅 결과, 접힘 | reward_detail |
| **landscape-loot-double-revealed** | S6 더블루팅 결과, 펼침 | reward_retry |
| **landscape-loot-double-scrolled** | S6 스크롤해야 보이는 `더블 루팅 전리품` 섹션 | (기록 불가) |

**S2 vs S5 구분**: 둘 다 `장면 넘기기`지만 S2는 보스 이름이 함께 뜬다(실측: "광기에 휩싸인 자이언트 헤드리스").
**OCR 오독 실측**: `던전 클리어!` → `던전 플리어!`. clear_touch가 이 문구를 requiredText로 안 쓰고 `화면을 터치해 주세요`(cf 1.0)만 쓰는 게 옳았음이 확인됨.

## 2026-07-26 갱신 — 실측으로 뒤집힌 것들

### ① OCR 신뢰도는 프레임마다 흔들린다 (멈춤의 진짜 원인)
같은 고정 이미지를 다시 읽어도 값이 달라진다. 실측:

| 글자 | 어제 | 오늘 |
|---|---|---|
| `다시 하기` | 1.00 | **0.50** |
| `입장하기` | 0.50 | **0.30** |
| `마비노기 모바일`(창 제목) | 1.00 | **0.50 → 0.30** |

`clear_touch`·`reward_retry`가 문턱 **0.85**로 전체 규칙 중 가장 높았고,
신뢰도가 흔들리면 그 둘만 골라서 안 잡혀 그 화면에서 멈췄다(2회 재현).

**교훈: 시그니처가 고유 문장이고 exact-match를 하면 글자 자체가 이미 필터다.**
신뢰도 문턱은 중복 방어였는데 오히려 멈춤을 만들었다. 전부 0.45 이하로 내렸다.
`mission_selection`만 예외였다가 아예 제거됐다(아래 ③).

### ② 언어 보정을 끄면 안 된다
`usesLanguageCorrection = false`는 40% 빠르지만(392→233ms) 글자가 흔들린다.
실측: `장면 넘기기` → `장면 넘기기_`. 이 문자열은 컷신 감지이자 **다른 모든 규칙의
컷신 차단 가드**라, 어긋나면 컷신을 못 넘기는 데다 컷신 중 오클릭까지 열린다.
판당 1.5초를 주고 되돌렸다.

### ③ 은동전이 새던 구멍 (실측 2026-07-26 13:16:50)
옵션이 꺼져 있는데 임무를 해제하지 않고 입장해 10개가 나갔다(해제 42회 : 입장 43회).
`enter_ready`를 막던 게 둘 다 불안정했다 — 25자 안내문 완전일치(은동전 10+ 화면엔
아예 없다), OCR이 코인 숫자를 버튼에 붙여 `10 입장하기`로 읽어 주기를 바라는 것.
**`선택됨`을 forbidden에 추가**했다. 3글자에 선택 상태에서만 뜬다.

`mission_selection`("도전")도 제거했다. 실측 세 상태를 다 보니 이 버튼이 눌릴 수
있는 유일한 경우가 "임무만 선택된 화면의 더블 루팅 도전"이었다 — 누르면 20개가 된다.

### ④ 더블 루팅 (미지원, 무조건 끈다)
```
A 둘 다 해제  임무 [도전]   더블루팅 [도전]   총 탐험 전리품  🪙0
B 임무만      임무 [선택됨] 더블루팅 [도전]   총 임무 전리품  🪙10
C 둘 다 선택  임무 [선택됨] 더블루팅 [선택됨] 총 임무 전리품  🪙20
```
C에서 `선택됨`이 둘이라 "정확히 하나" 조건이 깨져 후보 없이 멈췄다.
`turn_off_double_loot`가 끈다. 어느 쪽인지 가르는 데 **좌표를 안 쓴다** —
창 비율이 바뀌면 깨진다. 카드 안에 늘 있는 안내문을 기준선으로 삼는
`targetBelowText`를 뒀다. 세로로 쌓인 카드라 위아래 순서는 비율과 무관하다.

**지원 못 하는 이유**: 전리품의 절반이 `더블 루팅 전리품`이라는 별도 섹션에 있고
**스크롤해야 보인다.** 앱은 클릭만 하고 스크롤을 못 한다. 스크롤을 구현하면 그때
옵션으로 연다.

### ⑤ 침묵 감시기
상태가 `.observing`인 채 굳으면 겉보기엔 정상이라 몇 분씩 그냥 흘렀다.
150초 동안 후보를 못 찾으면 메뉴바를 `확인 필요`로 바꾸고 화면을 PNG로 남긴다
(`stall-YYYYMMDD-HHmmss.png`, 최근 20장). 임계값은 정상 파밍의 침묵 최대치
(실측 132판, 입장→보스컷신 최대 77초)의 두 배다.

### ⑥ 반응 시간 — 짐작 세 번 중 두 번이 틀렸다
| 시도 | 근거 | 결과 |
|---|---|---|
| OCR 보정 끄기 | 짐작 | 효과 있었으나 정확도로 되돌림 |
| 캡처 스트림 리팩터 | 짐작 | **착수 전 계측이 반증**(107ms만 절약) |
| `onScreenWindowsOnly: true` | 계측 | **398→269ms, 32% 단축** |

진짜 비용은 시스템 창 230개를 매번 훑는 데 있었다. 한 줄 변경.
`BackgroundAutomatorProbe bench-capture --bundle-id <id>`로 언제든 다시 잰다.

**앱이 13시간 연속 돌면 느려진다(정황)**: 화면 읽기 378ms → 932ms.
프로세스를 새로 띄우니 410ms로 돌아왔다. 재현되면 주기적 재시작이 답이다.

### ⑦ 자동시작 규칙은 넣으면 안 된다
던전 입장 직후 3~4초 게이지가 차면 자동 전투가 시작된다. 그 버튼은 **토글**이라
시작된 뒤에 누르면 **전투가 멈춘다.** 앱의 클릭이 3,956ms 걸려 늘 늦었다. 규칙 제거.

### ⑧ 전리품 이름 파싱
- 수량 뱃지가 이름으로 섞였다(`255.3만`) — 단위 `만`이 한글이라 한글 필터를 통과.
  숫자·단위 말고 다른 글자가 하나라도 있어야 이름으로 본다(`만병통치약`은 살아남음).
- 아이콘 밑에 이름이 두 줄로 쌓이면 OCR이 따로 준다(`세공된 블루`/`스피넬Z`).
  같은 칸에서 글자 높이 두 배 안쪽의 아랫줄을 잇는다. 좌표 상수 없이 글자 높이로 잰다.
- **남은 한계**: 가로로 붙은 이름을 한 덩어리로 줄 때가 있다
  (`조각난 에메랄드 조각난 사파이어 조각난 토파즈` 한 줄). 분리 기준을 못 세웠다.

## 열린 항목
- **전리품 스크롤 기록** — 더블 루팅 지원의 전제. `CGEvent` 스크롤 필요.
- **가로 병합 이름 분리** — 위 ⑧의 남은 한계.
- **정확 수량** — `공명의 영혼석`만 뱃지가 없다. "뱃지 없음 = 1"은 성립 안 함.
  등장 여부(드랍률)는 이름만으로 정확하다.
- **골든 커버리지** — 다른 창 비율(portrait 등) 대응.
- **테스트 병렬 실행** — 42개가 동시에 OCR을 요청하면 교착된다. `--no-parallel` 필수.

## 캡처 참조 (scratchpad, 세션 한정)
loot3.png=발견전리품 / silver10-selected.png=10+입장(안내문 없음) / silver-available.png=10+입장 초기 / exit-retry-next.png=전투복귀.
