# 데이터 출처와 제약

출처는 mabimobi.life 비공식 API 4종이다.

| 엔드포인트 | 쿼터 |
|---|---|
| `GET /d/api/v1/market/prices?limit=500&offset=N` | 없음 (실측 1,226건 / 1.7초) |
| `GET /d/api/v1/items?search=<말머리>&limit=200` | 없음 |
| `GET /d/api/v1/items/<id>` | **있음** — IP 단위 |
| `GET /d/api/v1/market/prices/history?kind_id=&interval=` | 없음 (일봉 55건 · 주봉 8 · 월봉 3) |

**캔들 API만 다른 키를 쓴다.** 거래소가 쓰는 진짜 `kind_id`(`281479538461834` 같은 큰 수)를 요구해서, `codex_item_id`를 넘기면 404다. 시세를 받을 때 `price_history.market_kind_id`에 함께 저장한다.

## 지켜야 할 것

### 원본이 자동 접근을 거절한다

`robots.txt`가 `User-agent: * / Disallow: /`이고 검색엔진·광고 크롤러만 허용한다. 공개로 돌리기 전에 [배포 문서](deploy.md)의 "원본 사이트의 방침"을 읽을 것.

### OpenSSL 3.x로 빌드된 파이썬으로 돌린다

원본은 Cloudflare 뒤에 있고 낡은 TLS 라이브러리를 막는다. 2026-08-19 실측:

| 파이썬 | ssl | 결과 |
|---|---|---|
| `/usr/bin/python3` 3.9.6 (macOS 기본) | LibreSSL 2.8.3 | **403** |
| `/opt/homebrew/bin/python3` 3.14.3 | OpenSSL 3.6.3 | 200 |
| macOS `curl` 8.7.1 | SecureTransport | **403** |

요청 횟수와 무관하다 — 손으로 한 번만 보내도 막힌다. TLS 버전 문제도 아니다(OpenSSL 쪽을 TLS 1.2로 낮춰도 200). `ssl.OPENSSL_VERSION`으로 확인한다.

### 레시피는 1회만 받는다

상세 API에만 쿼터가 걸리고, 레시피는 게임 패치 전까지 바뀌지 않는다. 실측에서 한 번에 39종을 받고 끊겼다. `collect.py recipes`는 받은 만큼 유지하고 다음 실행에서 못 받은 것부터 잇는다 — 76종을 39 + 37로 나눠 받았다.

### 끊기면 바로 재시도하지 마라

429 본문이 `Expected available in N seconds`를 주지만 그 시간이 지나도 안 풀린다. 5분 간격 8회(약 40분) 재시도에서 한 건도 더 받지 못했고, 몇 시간 뒤에야 풀렸다. 끊기면 그날은 두고 나중에 `collect.py recipes`를 다시 부르는 게 빠르다.

### 게임 클라이언트 패킷은 쓰지 않는다

약관 위반이고, 필요한 데이터가 이미 API에 있다.

## 시세 이력은 94종만 쌓는다

원본은 시세를 1,199~1,226종 통째로 준다(종목 필터가 없어 다 받고 우리가 버린다). 그중 화면에 쓰는 건 재료 18종과 잔영·해연 76종뿐이고 나머지 92%는 가구·요리·데코다.

전부 쌓았더니 하루 71MB씩 늘어 닷새 만에 329MB가 됐고 조회가 4.3초로 늘어졌다. 필터를 건 뒤 24MB · 0.017초.
