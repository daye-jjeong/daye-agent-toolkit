# 장시간 작업 대기

CI/CD, Docker, 배포 대기 시:
- `gh run watch` 등 연속 출력 대신 지수 백오프 (1m→2m→4m→8m max)
- 확인은 한 줄 (`gh run view <id> | grep <job>`)
- 토큰 낭비 최소화
