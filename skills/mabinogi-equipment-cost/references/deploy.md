# 웹에 띄우기

## 먼저 — 원본 사이트의 방침

**mabimobi.life의 `robots.txt`는 자동 접근을 거절한다.**

```
User-agent: *
Disallow: /

User-agent: Googlebot / Bingbot / Naverbot / Yeti / DuckDuckBot / Daum   Allow: /
User-agent: Mediapartners-Google / Google-Display-Ads-Bot                Allow: /
```

검색엔진과 **광고 크롤러**만 허용한다. 이 도구는 `User-agent: *`에 해당하므로 그 방침에 어긋난다.

부담 때문이 아니다. 우리 트래픽은 하루 1,458회 · 279MB(평균 0.026Mbps)로 그쪽 방문자 수백 명이 페이지 한 번 여는 정도다. 실제로 그들이 막은 것도 횟수가 아니라 클라이언트 지문이었다 — 손으로 한 번만 보내도 403이다.

그들이 잃는 건 대역폭이 아니라 이거다. 페이지에 `adsbygoogle`이 박혀 있다 — **광고로 굴러가는 사이트**인데, 우리는 데이터만 가져가고 광고는 안 본다. 애널리틱스에도 안 잡힌다.

그래서 남에게 열기 전에 정할 것:

1. 운영자에게 문의해 허락을 구한다 (부담이 미미하다는 게 협상에 유리하다)
2. 허락이 없으면 개인용으로만 쓰고 공개 주소를 돌리지 않는다

**차단을 우회할 방법을 찾는 쪽으로 가지 마라.** 저쪽은 두 번 거절했다 — `robots.txt`로 한 번, 실제 차단으로 한 번.

## 로컬과 `--public`

여러 사람이 쓰게 하려면 `--public`으로 띄운다. 로컬판과 셋이 다르다.

| | 로컬 | `--public` |
|---|---|---|
| 바인딩 | `127.0.0.1` | `0.0.0.0` |
| 새로고침 버튼 | 있다 | **없다** (`POST /refresh`도 404) |
| 시세 수집 | 버튼을 누르거나 `collect.py loop` | 서버가 3분마다 직접 |
| 신선도 임계 | 30분 | 15분 (주기의 5배) |

버튼을 남기면 방문자마다 원본 API로 요청이 나가고, 그게 **서버 IP 하나**로 몰린다. 상세 API에서 이미 IP 쿼터를 겪었다 — 한 번에 39종에서 끊겼고 몇 시간 뒤에야 풀렸다.

재고는 방문자의 브라우저 쿠키에 산다. 서버는 누가 뭘 가졌는지 모른다.

## 쿼터는 배포에 걸리지 않는다

IP 단위 쿼터가 있는 건 **상세 API**(`/items/<id>`)뿐이고, 그건 레시피를 받을 때만 쓴다. 씨앗 DB에 레시피가 이미 들어 있으면 배포판은 그 엔드포인트를 **한 번도 부르지 않는다** — `serve.py --public`이 부르는 건 `collect_prices` → `fetch_prices`, 즉 쿼터 없는 시세 API 하나다.

그래서 방문자가 늘어도 원본에 대한 부하는 그대로다. 서버가 3분에 한 번 1,226건(1.7초)을 받고 모두가 그 결과를 나눠 본다.

쿼터를 다시 만나는 경우는 하나 — **씨앗 없이 배포하고 배포처에서 `collect.py recipes`를 돌릴 때**다. 그러지 마라.

## 필요한 것

셋뿐이다.

- **항상 켜져 있을 것** — 3분마다 시세를 받는 스레드가 돈다. 잠들면 화면이 낡는다
- **디스크** — SQLite 파일 하나. 재시작 때마다 초기화되면 시세 이력이 안 쌓인다
- **바깥으로 나가는 HTTPS** — mabimobi.life를 부른다
- **OpenSSL 3.x로 빌드된 파이썬** — 아래 참조

파이썬 표준 라이브러리만 쓰므로 설치할 패키지가 없다.

### 파이썬을 아무거나 쓰면 403이 난다

원본이 Cloudflare 뒤에 있고, 낡은 TLS 라이브러리로 붙으면 막는다. 2026-08-19 실측:

| 파이썬 | ssl | 결과 |
|---|---|---|
| `/usr/bin/python3` 3.9.6 (macOS 기본) | LibreSSL 2.8.3 | **403** |
| `/opt/homebrew/bin/python3` 3.14.3 | OpenSSL 3.6.3 | 200 |
| `~/miniconda3/bin/python3` 3.12.2 | OpenSSL 3.5.4 | 200 |
| macOS `curl` 8.7.1 | SecureTransport | **403** |

TLS 버전 문제가 아니다 — OpenSSL 쪽을 일부러 TLS 1.2로 낮춰도 200이다. HTTP 요청 바이트도 두 인터프리터가 완전히 같다. 남는 차이는 핸드셰이크 첫 인사의 생김새고, Cloudflare가 그걸 지문으로 쓴다.

확인하는 법:

```bash
python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"
```

`LibreSSL`이 나오면 그 파이썬으로는 못 돌린다. Docker(`python:3.12-slim`)는 OpenSSL 3.x라 문제없다.

**`python3`를 PATH에 맡기지 마라.** 어느 셸에서 띄웠느냐로 갈린다 — 실제로 그래서 배포판이 3.9로 떠 있다가 원본이 규칙을 조인 순간 50분간 멈췄다.

## 어디에 띄우나

| 곳 | 비용 | 맞나 |
|---|---|---|
| 집 맥 + Cloudflare Tunnel | 0원 | 가장 빨리 된다. 맥이 켜져 있어야 하고, 잠들면 같이 멈춘다 |
| Oracle Cloud Always Free | 0원 | 항상 켜진 VM + 디스크. 요구사항 셋을 다 채운다. 계정 만들기가 번거롭고 유휴 인스턴스를 회수한 사례가 있다 |
| Render 무료 | 0원 | **안 맞는다.** 유휴 15분이면 잠들어 수집이 멈추고, 디스크가 임시라 재배포마다 시세가 날아간다 |
| Fly.io | 월 $2 안팎 | 무료 티어는 2024년에 없어졌다. 항상 켜짐이 필요하면 가장 싼 유료 |

오래 둘 거면 **Oracle Cloud Always Free**, 며칠 써 보고 정할 거면 **집 맥 + Cloudflare Tunnel**이 빠르다.

## 씨앗 DB

레시피는 배포처에서 다시 받지 마라. 상세 API 쿼터 때문에 76종을 39 + 37로 나눠 받는 데 몇 시간이 걸린다. 이미 받아 둔 것을 들고 간다.

```bash
python3 scripts/collect.py seed ~/.mabi-equipment-cost/data.db deploy/seed.db
```

실측 88KB다(원본 1.2MB). 시세 이력은 빠진다 — 쿼터가 없어 서버가 뜨고 3분 안에 스스로 채운다. 재고 테이블이 남아 있어도 따라가지 않는다.

## Docker

`deploy/Dockerfile`이 있다. 스킬 루트에서 빌드한다.

```bash
docker build -f deploy/Dockerfile -t mabi-cost .
```

```bash
docker run -p 8765:8765 mabi-cost
```

플랫폼이 `$PORT`를 주면 그 포트를 쓴다. 디스크를 붙이려면 `/data`에 마운트한다.

## 집 맥 + Cloudflare Tunnel

```bash
python3 scripts/serve.py 8765 --public
```

```bash
cloudflared tunnel --url http://localhost:8765
```

`trycloudflare.com` 주소가 하나 나온다. 계정 없이 되고, 고정 주소가 필요하면 Cloudflare 계정에 터널을 등록한다.

**맥이 잠들면 서버도 멈춘다.** `caffeinate -s`로 띄워 두거나 전원 설정에서 잠자기를 끈다.

### 감시 루프

서버가 죽어도 되살아나게 `deploy/keepalive.sh`를 함께 띄운다.

```bash
cp deploy/keepalive.sh ~/.mabi-equipment-cost/keepalive.sh
```

```bash
nohup bash ~/.mabi-equipment-cost/keepalive.sh "$PWD" ~/.mabi-equipment-cost/server.log &
```

20초마다 `serve.py`가 살아 있는지 보고 없으면 다시 띄운다. 파이썬 경로가 안에 박혀 있고(`MABI_PYTHON`으로 바꿀 수 있다), 다른 맥에 옮기면 그 경로부터 고쳐야 한다.

**`cloudflared`는 건드리지 않는다.** 터널이 `localhost:8765`를 보므로 서버만 다시 뜨면 같은 주소로 이어진다. 터널을 재시작하면 `trycloudflare.com` 주소가 **영구히 바뀐다.**

주의 둘:

- **돌고 있는 `keepalive.sh`를 그 자리에서 고치지 마라.** bash는 스크립트를 바이트 오프셋으로 읽어서, 길이가 바뀌면 루프가 어긋나 죽는다(실측: 그렇게 13분 다운). 고쳤으면 루프를 죽였다가 새로 띄운다.
- **launchd에 등록돼 있지 않다.** 맥을 재부팅하면 서버·감시 루프·터널이 전부 안 뜨고, 터널이 새로 뜨면서 주소도 바뀐다.

코드를 고친 뒤 배포에 반영하려면 서버만 죽이면 된다. 감시 루프가 20초 안에 새 코드로 되살린다.

```bash
pkill -f "serve.py 8765 --public"
```

## 남에게 열기 전에 알아 둘 것

- **레시피가 이미 다 차 있어야 한다.** 씨앗을 안 만들고 띄우면 첫 화면이 "수집 중" 투성이고, 채우려면 쿼터 때문에 몇 시간이 든다
- **원본이 자동 접근을 거절한다.** 맨 위 "원본 사이트의 방침"을 먼저 읽을 것
- **비공식 API다.** 원본이 막거나 응답을 바꾸면 페이지가 낡은 값에서 멈춘다. 상단 신선도 띠가 그걸 알린다 — 15분을 넘으면 노랗게 바뀐다. 2026-08-19에 실제로 그랬다(Cloudflare가 구식 TLS 클라이언트를 막기 시작)
- **개인 데이터를 받지 않는다.** 계정도 로그인도 없고, 쿠키에 든 건 재료 수량뿐이다
