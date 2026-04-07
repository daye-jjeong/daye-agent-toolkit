# 주간 AI 예측

뉴스페이퍼 아카이브 데이터 기반 AI 산업 주간 예측. 자가개선 루프 포함.

- DB: `~/.local/share/news-brief/forecast.db`
- 크론: 매주 월요일 09:00 KST (`0 9 * * 1`)

## 아카이브 (매일 자동)

뉴스페이퍼 생성 후 enriched JSON을 DB에 적재:

```bash
python3 {baseDir}/scripts/archive.py --input /tmp/enriched.json
```

## 주간 예측 절차 (크론 에이전트용)

1. 검증 데이터 추출:
   ```bash
   python3 {baseDir}/scripts/forecast.py verify > /tmp/forecast_verify.json
   ```
2. `/tmp/forecast_verify.json`의 각 prediction을 검토. 해당 기간 기사 목록을 근거로 hit/miss/expired 판정:
   ```bash
   python3 {baseDir}/scripts/forecast.py update-status --id <id> --status hit|miss|expired --verification "판정 근거"
   ```
3. 분석:
   ```bash
   python3 {baseDir}/scripts/forecast.py analyze --week <YYYY-Wnn> > /tmp/forecast_analyze.json
   ```
4. 시그널 추출:
   ```bash
   python3 {baseDir}/scripts/forecast.py signals > /tmp/forecast_signals.json
   ```
5. `forecast_analyze.json`의 `bias_notes`와 `weekly_trend`를 참고하여 과거 편향 인지
6. 시그널 + 과거 교훈을 기반으로 예측 3~5개 생성 (claim, confidence 0.0-1.0, reasoning, deadline)
7. 예측을 DB에 저장 (forecast.py의 save_predictions 함수 또는 직접 SQL)
8. 리포트 포맷팅:
   ```bash
   python3 {baseDir}/scripts/forecast.py report \
     --week <YYYY-Wnn> \
     --signals /tmp/forecast_signals.json \
     --verify /tmp/forecast_verify.json \
     --analyze /tmp/forecast_analyze.json \
     --predictions /tmp/forecast_predictions.json
   ```
9. 결과를 텔레그램으로 전송
