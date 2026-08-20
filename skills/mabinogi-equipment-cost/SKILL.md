---
name: mabinogi-equipment-cost
description: 마비노기 모바일 잔영·해연 장비 76종의 거래소 최저가와 제작 재료비를 한 표로 비교. 사는 게 싼지 만드는 게 싼지, 재료 중 뭐가 원가를 지배하는지 본다. "잔영 해연 원가", "장비 제작이 싼가", "마비노기 거래소 비교" 요청에 사용.
---

## 무엇을 답하나

**해연 한 종을 제일 싸게 손에 넣는 길**을 고른다. 행은 해연 38종, 각 종마다 네
길을 한 줄에 세운다:

| 길 | 뜻 |
|---|---|
| 해연 구매 | 완제품을 그냥 산다 |
| 해연 제작 | 레시피 없이 만든다 |
| 잔영×N 구매 | 같은 종류 잔영을 배수만큼 산다 |
| 잔영×N 제작 | 같은 종류 잔영을 배수만큼 만든다 |
| 가장 싼 길 | 넷 중 최저 + "해연 그냥 살 때보다 얼마 아끼나" |

배수(기본 10)가 판정을 크게 흔든다. 행을 펼치면 경로별 재료 수량·단가·소계·매물
수가 나와 원가를 지배하는 재료가 보인다.

## 쓰는 법

```bash
python3 scripts/run.py collect items      # 아이템 목록 (1회면 충분)
python3 scripts/run.py collect recipes    # 레시피 — 쿼터 걸리면 반복 실행
python3 scripts/run.py collect prices     # 시세 1회
python3 scripts/run.py                     # 원가표 서버 (http://localhost:8765)
```

시세를 주기로 갱신: `python3 scripts/run.py collect loop ~/.mabi-equipment-cost/data.db 180`.

## 구조

이 스킬은 **얇은 진입점**이다. `scripts/run.py`가 레포 루트를 찾아 실제 프로그램을
실행한다. 코드 본체·상세 문서는 `apps/mabinogi/equipment-cost/`에 있다:

- `scripts/` — `collect.py`(수집)·`serve.py`(원가표 서버)·`cost.py`·`store.py` 등
- `README.md` — 무엇을 답하나·판정 규칙·배수 상세
- `references/` — 시세/표 읽는 법, API 제약, 배포(`deploy.md`)
- `deploy/` — Docker·keepalive (Cloudflare Tunnel 배포)

## 데이터 — 플랫폼 시세 공급원

`collect.py`가 거래소 시세를 `~/.mabi-equipment-cost/data.db`에 쌓는다. 이 시세를
[[mabinogi-farming]] 대시보드가 읽어 영혼석 데카를 매긴다. 즉 이 스킬은 원가 비교
도구이자 **마비노기 데이터 플랫폼의 시세 수집원**이다. 데이터 계약은
`apps/mabinogi/README.md`.
