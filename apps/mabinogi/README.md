# 마비노기 데이터 플랫폼

마비노기 모바일 플레이 데이터를 **모으고 · 쌓고 · 분석하는** 우리 프로그램 묶음.
계속 확장한다 — 수집원도, 분석 측면도 늘어난다. 그래서 역할을 나눠 둔다.

## 세 역할

```
수집(collector)  →  저장(store, ~/.mabi/)  →  분석(analyzer)
```

- **수집기는 쓰고, 분석기는 읽는다.** 분석기가 수집기 내부를 직접 뒤지지 않는다.
- 경로·위치는 [`shared/mabi/data.py`](shared/mabi/data.py) 한 곳에서만 정한다.
  하드코딩을 산재시키지 않는다.
- **데이터는 레포 밖(`~/.mabi/`)에 산다.** 런타임 데이터가 git을 더럽히지 않고,
  worktree마다 쪼개지지 않으며(단일 store), `make install`이 딸려가지 않는다.
  선례: `~/life-dashboard/data.db`.

## 디렉터리

```
apps/mabinogi/
├── README.md            이 문서 — 데이터 계약(단일 진실)
├── shared/mabi/data.py  store 경로 해석 + MABI_HOME override
├── m-agent/            [수집·Swift]  게임 자동화 + 플랫폼 메뉴바 → 파밍 로그
├── equipment-cost/      [제품]        시세 수집 + 원가 분석
└── farming/             [제품]        파밍 로그 분석 + 대시보드
```

제품(자립 실행 단위)이 1차 축이다. collector·analyzer는 **제품 안의 모듈**이지,
따로 찢어 놓은 트리가 아니다 — 한 제품의 코드·테스트가 두 곳에 흩어지지 않게.

스킬(`skills/mabinogi-*`)은 **얇은 진입점**이다. 자체 `scripts/run.py`가 레포 루트를
`Path(__file__).resolve()`로 찾아 여기 프로그램을 실행한다. 코드 본체는 여기 있고,
스킬은 부를 수 있게만 한다.

## 데이터 계약 (버전 1)

데이터 홈은 `~/.mabi/`. `MABI_HOME` 환경변수로 덮어쓴다(테스트·임시 실행).
store는 **생산자 소유 서브디렉터리**에 산다 — 쓰는 프로그램의 이름을 딴다.

```
~/.mabi/
├── m-agent/            m-agent(Swift)가 쓰는 전부
│   ├── cycle-log.jsonl     [store] 파밍 로그 — reader: farming
│   ├── rules.json          앱 규칙 오버라이드
│   └── status.json · activity-log.jsonl · builds.jsonl · stall-log.jsonl · stall-*.png
│                           앱 운영 진단 (공유 데이터셋 아님, 앱 전용)
└── equipment-cost/     시세 수집기가 쓰는 것
    └── prices.db           [store] 시세 — reader: farming, equipment-cost
```

| store | 경로 | 포맷 | writer | reader |
|---|---|---|---|---|
| 파밍 로그 | `~/.mabi/m-agent/cycle-log.jsonl` | JSONL(판당 1줄) | m-agent(Swift) | farming |
| 시세 | `~/.mabi/equipment-cost/prices.db` | SQLite | equipment-cost 수집기 | farming, equipment-cost |

분석기(farming)는 store를 만들지 않는다 — 읽기만. store는 수집기·앱만 만든다.

**파밍 로그 레코드** — 한 판: `{at(ISO UTC), dungeon, entry?, items[], quantities{}, mode?}`.
`items`는 전리품 슬롯 문자열, `quantities`는 수량 뱃지, `mode`는 재화/무료 오버라이드.

**시세** — 테이블 `price_history(name, min_price, as_of, …)`. 분석기는 최신 `as_of`의
행만 읽기 전용으로 본다.

### 경로 해석 (구 경로 호환)

`shared/mabi/data.py`는 "새 경로에 파일이 있으면 그것, 없으면 구 경로"로 푼다.
구 위치 — 파밍 로그는 `~/Library/Application Support/BackgroundAutomator/`, 시세는
`~/.mabi-equipment-cost/data.db`. 데이터가 새 홈으로 옮겨가면 소비자 코드를 안
고쳐도 자동으로 새 경로를 쓴다. Swift도 `MABI_HOME`을 따른다(Python과 parity).

## 이관 단계

| 단계 | 범위 | 상태 |
|---|---|---|
| 0 | 플랫폼 뼈대 + README 계약 + `shared/mabi/data.py`(구 경로 fallback) | ✅ |
| 1 | farming 한 단위 이동 + `shared/mabi` 사용 + `mabinogi-farming` 스킬 | ✅ |
| 3 | `background-automator` → `m-agent`로 개명(폴더·패키지·번들ID·표시명) + 데이터 `~/.mabi/m-agent/`로 | ✅ (코드) |
| 2 | equipment-cost 코드 → `apps/mabinogi/equipment-cost/` + 얇은 스킬 | ✅ (코드) |

**데이터 이사(cutover)는 런타임 단계로 남는다.** 코드는 새 경로를 쓰지만, 실제 데이터를
옮기고 프로그램을 재시작해야 완결된다. `shared/mabi/data.py`가 새 경로 없으면 구 경로로
읽어(fallback) 그 사이에도 안 깨진다.
- **m-agent**: 새 앱(개명·번들ID 변경)을 설치·실행하면 `~/.mabi/m-agent/`에 쓴다. 구
  `~/Library/Application Support/BackgroundAutomator/` 데이터를 복사해 오는 게 이사.
  번들ID가 바뀌어 macOS 권한(화면기록·손쉬운사용·입력모니터링) 재등록이 필요하다.
- **equipment-cost 시세**: 수집기를 `~/.mabi/equipment-cost/prices.db`로 돌리면 이사 완료
  (2026-08-20 그렇게 세팅함). 구 `~/.mabi-equipment-cost/data.db`는 다른 세션이 아직 씀.
- 구 경로 fallback 제거는 각 writer 전환·검증을 마친 **뒤 별도 단계**.

2단계는 다른 브랜치(`mabi-material-price-chart`)가 equipment-cost를 활발히 고치는 중에
진행했다 — 그 브랜치가 머지될 때 `skills/mabinogi-equipment-cost/scripts/` →
`apps/mabinogi/equipment-cost/scripts/` 이동에 맞춰 재적용해야 한다(git rename 감지가
대부분 자동 처리).

## 알려진 계약 공백 (확장 전에 채운다)

- 파밍 로그 레코드에 **스키마 버전이 없다.** 시세 DB에도 `user_version`이 없다.
  외부 소비자가 늘기 전에 버전 필드/정책을 넣는다(레코드 version, DB user_version).
- 계약의 단일 진실은 이 README다. Python(`shared/mabi/data.py`)과 Swift 구현이
  갈리지 않게 양쪽에 **계약 테스트**를 둔다.
