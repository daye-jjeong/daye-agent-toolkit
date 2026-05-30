# 토큰 효율

- grep 전 자문: 파일 위치 알면 바로 Read. 모르면 files_with_matches로 특정 후 Read. broad grep으로 20KB+ 결과 금지.
- 심볼 탐색(정의·참조·호출처·구현체)은 grep 전 LSP: goToDefinition/findReferences/incomingCalls/goToImplementation. grep은 텍스트·패턴(문자열·주석·설정값)에만.
- 변경 30% 미만이면 Write 대신 Edit. 같은 파일 변경은 한 번에 묶어서.
- Explore 에이전트: 대상 파일을 알거나 grep 2~3개로 찾으면 쓰지 마라.
