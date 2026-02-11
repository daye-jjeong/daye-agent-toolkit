# vault-memory:preserve

> 중요한 정보를 `~/mingming-vault/memory/MEMORY.md`에 영구 저장한다.

**기록 규격**: `~/mingming-vault/memory/format.md` § 3 참조

## 트리거

- "기억해줘", "preserve", "메모리에 저장", "영구 저장"
- compress 중 장기 보관 가치 발견 시 자동 제안

## 워크플로우

### 1. 저장할 내용 확인

사용자에게 확인:
- 무엇을 저장할지
- 어떤 섹션에 넣을지 (기존 섹션 or 새 섹션)

### 2. MEMORY.md 읽기

`~/mingming-vault/memory/MEMORY.md` 현재 내용을 읽고 구조 파악.

### 3. 섹션 분류

**보호 섹션** (구조 변경 금지, 내용 추가만):
- Career/Compensation
- Health Notes
- System/Operations
- Key/Auth Management

**이동 가능 섹션** (재배치, 아카이브 가능):
- Investing Research
- Budget/Finance
- 기타 시한성 정보

### 4. 항목 추가

- 해당 섹션 찾아서 적절한 위치에 추가
- 섹션 없으면 새로 생성 (이동 가능 섹션으로)
- 중복 체크: 유사 내용 있으면 업데이트 제안

### 5. 줄 수 체크

- **350줄 이하**: 정상 저장
- **350줄 초과**: 아카이브 제안
  - 이동 가능 섹션 중 가장 오래된 것 → `~/mingming-vault/memory/archive/MEMORY-YYYY-MM.md`
  - 사용자 승인 후 실행

### 6. 저장 확인

- `updated_by`, `updated_at` 갱신
- 변경 내용 요약 출력

## 주의사항

- 민감 정보 마스킹 (API 키, 비밀번호 → `****`)
- 보호 섹션 기존 내용 삭제 금지
- 아카이브는 반드시 사용자 승인 후
