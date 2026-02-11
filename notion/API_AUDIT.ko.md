# Notion API 감사 (2025-09-03)

**날짜:** 2026-02-03
**API 버전:** 2025-09-03
**클라이언트 버전:** 0.2.0

## 요약

이 감사는 공식 Notion API (버전 2025-09-03)와 우리의 NotionClient 구현을 비교하여 격차를 식별하고 구현 우선순위를 정합니다.

**상태:** ✅ 핵심 기능 구현 완료, 파일 업로드 추가, 아카이브/복원 추가

**우선순위 범례:**
- **P0** (긴급): 필수 기능, 즉시 구현 필요
- **P1** (높음): 중요한 기능, 1-2주 내 구현
- **P2** (중간): 있으면 좋음, 필요에 따라 구현
- **P3** (낮음): 엣지 케이스, 요청이 없으면 연기

## 구현 상태

### ✅ 구현 완료 (핵심)

| 기능 | Endpoint | 상태 | 비고 |
|---------|----------|--------|-------|
| Get page | `GET /v1/pages/{id}` | ✅ | `get()` 사용 |
| Update page | `PATCH /v1/pages/{id}` | ✅ | `update_page()` |
| Archive page | `PATCH /v1/pages/{id}` | ✅ 신규 | `archive_page()` |
| Restore page | `PATCH /v1/pages/{id}` | ✅ 신규 | `restore_page()` |
| Create page | `POST /v1/pages` | ✅ | `create_page()` |
| Get block | `GET /v1/blocks/{id}` | ✅ | `get()` 사용 |
| Update block | `PATCH /v1/blocks/{id}` | ✅ | `patch()` 사용 |
| Archive block | `PATCH /v1/blocks/{id}` | ✅ 신규 | `archive_block()` |
| Restore block | `PATCH /v1/blocks/{id}` | ✅ 신규 | `restore_block()` |
| Delete block | `DELETE /v1/blocks/{id}` | ✅ | `delete()` 사용 |
| Get block children | `GET /v1/blocks/{id}/children` | ✅ | `get()` 사용 |
| Append block children | `PATCH /v1/blocks/{id}/children` | ✅ | `append_blocks()`, `append_blocks_batch()` |
| Get database | `GET /v1/databases/{id}` | ✅ | `get_database()` |
| Query database | `POST /v1/databases/{id}/query` | ✅ | `query_database()` |
| Search | `POST /v1/search` | ✅ | `search()` |
| File upload | `POST /v1/file_uploads` | ✅ 신규 | `upload_and_attach_file()` |
| File upload complete | `POST /v1/file_uploads/{id}/complete` | ✅ 신규 | `_upload_file()` 내부 사용 |

### 🚧 부분 구현

| 기능 | 상태 | 격차 | 우선순위 | 비고 |
|---------|--------|-----|----------|-------|
| File upload (multipart) | ⚠️ 부분 | >20MB 파일 미지원 | P2 | 단일 파트 동작 (<20MB), multipart는 명확한 오류와 함께 스텁 처리 |
| Data sources (2025-09-03) | ⚠️ 부분 | 다중 소스 데이터베이스 미지원 | P1 | 기존 `query_database()`는 단일 소스 DB에서 작동 |

### ❌ 미구현

#### P0 (긴급) - 없음

모든 긴급 기능 구현 완료.

#### P1 (높은 우선순위)

| 기능 | Endpoint | 이유 | 구현 난이도 |
|---------|----------|--------|----------------------|
| **Data source query** | `POST /v1/data_sources/{id}/query` | 2025-09-03에서 다중 소스 데이터베이스 도입 | 중간 - 새 메서드 + 하위 호환성 필요 |
| **Get user** | `GET /v1/users/{id}` | @mention 해석, 소유권 확인에 필요 | 낮음 - 단순 GET 래퍼 |
| **List users** | `GET /v1/users` | 팀/권한 관리에 필요 | 낮음 - 페이지네이션이 있는 단순 GET |
| **Get comment** | `GET /v1/comments/{id}` | 협업 기능에 유용 | 낮음 - 단순 GET |
| **Create comment** | `POST /v1/comments` | 협업 기능에 유용 | 낮음 - 단순 POST |

#### P2 (중간 우선순위)

| 기능 | Endpoint | 이유 | 구현 난이도 |
|---------|----------|--------|----------------------|
| **Multipart file upload** | `POST /v1/file_uploads/{id}/send` | >20MB 파일 지원 | 중간 - 청킹 + 진행 추적 |
| **Create database** | `POST /v1/databases` | 거의 필요 없음 (보통 UI에서 수행) | 낮음 - 스키마와 함께 POST |
| **Update database** | `PATCH /v1/databases/{id}` | 스키마 변경은 보통 수동 | 낮음 - 스키마와 함께 PATCH |
| **Get page property** | `GET /v1/pages/{id}/properties/{property_id}` | 페이지네이션된 속성에 유용 | 낮음 - GET 래퍼 |
| **Webhook subscriptions** | `POST /v1/webhooks` | 실시간 업데이트 | 높음 - 서버 인프라 필요 |

#### P3 (낮은 우선순위)

| 기능 | Endpoint | 이유 | 구현 난이도 |
|---------|----------|--------|----------------------|
| **Bot info** | `GET /v1/users/me` | 정보 제공용 | 낮음 - 단순 GET |
| **Rich text parsing** | N/A (클라이언트 측) | 복잡한 포매팅 헬퍼 | 중간 - 파서 구현 |

## 상세 분석

### 1. Data Sources (2025-09-03 Breaking Change)

**변경 사항:**
- Notion이 이제 **데이터베이스당 여러 데이터 소스** 지원 (예: 외부 API에서 동기화)
- 기존 endpoint: `POST /v1/databases/{database_id}/query`
- 새 endpoint: `POST /v1/data_sources/{data_source_id}/query`

**현재 상태:**
- `query_database()`는 **단일 소스 데이터베이스**에서 여전히 작동 (하위 호환)
- `get_database()`는 이제 단일 소스 대신 `data_sources[]` 배열 반환

**권장사항 (P1):**
```python
def query_data_source(self, data_source_id: str, filter=None, sorts=None):
    """특정 데이터 소스 쿼리 (2025-09-03)"""
    payload = {}
    if filter:
        payload["filter"] = filter
    if sorts:
        payload["sorts"] = sorts
    return self.post(f"/v1/data_sources/{data_source_id}/query", json=payload)

def query_database_v2(self, database_id: str, filter=None, sorts=None):
    """
    데이터베이스 쿼리 (2025-09-03 호환)
    
    자동으로 데이터 소스를 가져와 첫 번째 소스를 쿼리합니다.
    다중 소스 데이터베이스의 경우 query_data_source()를 직접 사용하세요.
    """
    # 데이터베이스 메타데이터 가져오기
    db = self.get_database(database_id)
    
    # 첫 번째 데이터 소스 가져오기
    if not db.get("data_sources"):
        raise ValueError(f"Database {database_id} has no data sources")
    
    data_source_id = db["data_sources"][0]["id"]
    return self.query_data_source(data_source_id, filter, sorts)
```

### 2. File Upload (Multipart)

**현재 상태:**
- ✅ 단일 파트 업로드 작동 (<20MB)
- ❌ Multipart 업로드 미구현 (>20MB)

**사용 사례:** 대용량 PDF, 동영상, 아카이브

**권장사항 (P2):**
`/v1/file_uploads/{id}/send`를 사용한 청크 업로드 구현:

```python
def _upload_file_multipart(self, file_path: str, content_type: str, chunk_size=10*1024*1024):
    """청크로 대용량 파일 업로드 (기본 10MB)"""
    # 1. 업로드 생성
    create_resp = self.post("/v1/file_uploads", json={...})
    file_id = create_resp["id"]
    
    # 2. 청크 업로드
    with open(file_path, 'rb') as f:
        chunk_num = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            self.post(f"/v1/file_uploads/{file_id}/send", data=chunk, headers={
                "Content-Type": content_type,
                "Content-Range": f"bytes {chunk_num*chunk_size}-{chunk_num*chunk_size+len(chunk)-1}/{file_size}"
            })
            chunk_num += 1
    
    # 3. 업로드 완료
    self.post(f"/v1/file_uploads/{file_id}/complete", json={})
    return file_id
```

### 3. Users & Permissions

**현재 상태:** 미구현

**사용 사례:**
- 페이지의 @mention 해석
- 페이지 소유권 확인
- 팀 관리 자동화

**권장사항 (P1):**
```python
def get_user(self, user_id: str):
    """ID로 사용자 가져오기"""
    return self.get(f"/v1/users/{user_id}")

def list_users(self, start_cursor=None):
    """워크스페이스의 모든 사용자 나열 (페이지네이션)"""
    params = {}
    if start_cursor:
        params["start_cursor"] = start_cursor
    return self.get("/v1/users", params=params)

def get_bot_info(self):
    """현재 봇 사용자 정보 가져오기"""
    return self.get("/v1/users/me")
```

### 4. Comments

**현재 상태:** 미구현

**사용 사례:**
- 자동 리뷰 댓글
- 토론 스레딩
- 협업 워크플로우

**권장사항 (P1):**
```python
def create_comment(self, parent_id: str, rich_text: list, discussion_id=None):
    """페이지 또는 기존 토론에 댓글 생성"""
    payload = {
        "parent": {"page_id": parent_id},
        "rich_text": rich_text
    }
    if discussion_id:
        payload["discussion_id"] = discussion_id
    return self.post("/v1/comments", json=payload)

def get_comments(self, block_id: str, start_cursor=None):
    """블록의 댓글 나열"""
    params = {"block_id": block_id}
    if start_cursor:
        params["start_cursor"] = start_cursor
    return self.get("/v1/comments", params=params)
```

### 5. Database Creation/Modification

**현재 상태:** 미구현

**사용 사례:**
- 프로그래매틱 데이터베이스 설정
- 스키마 마이그레이션
- 템플릿 인스턴스화

**권장사항 (P2):**
구체적인 필요가 발생하기 전까지 연기. 데이터베이스 생성은 일반적으로 UI에서 수행됨.

## 권장사항 요약

### 즉시 (다음 PR)
1. ✅ **파일 업로드** - 구현 완료
2. ✅ **아카이브/복원** - 구현 완료

### 단기 (1-2주)
3. **Data source query** - 2025-09-03 호환성 (P1)
4. **사용자 관리** - `get_user()`, `list_users()` (P1)
5. **댓글** - `create_comment()`, `get_comments()` (P1)

### 중기 (필요에 따라)
6. **Multipart upload** - 대용량 파일 >20MB (P2)
7. **데이터베이스 생성** - `create_database()` (P2)

### 연기
8. **Webhooks** - 서버 인프라 필요 (P3)
9. **Rich text helpers** - 유용한 유틸리티 (P3)

## 테스트 커버리지

### 현재 테스트
- ✅ 파일 업로드 (단일 파트)
- ✅ 파일 업로드 오류 처리 (>20MB, 파일 누락)
- ✅ 컨텐츠 타입 감지
- ✅ 페이지 아카이브/복원
- ✅ 블록 아카이브/복원
- ✅ 재시도 로직 (429, 5xx)
- ✅ 워크스페이스 선택

### 필요한 테스트 (향후)
- Data source 쿼리 (구현 시)
- Multipart 업로드 (구현 시)
- 사용자 관리 (구현 시)
- 댓글 (구현 시)

## 변경 이력

**v0.2.0 (2026-02-03)**
- ✅ 파일 업로드 지원 추가 (`upload_and_attach_file()`)
- ✅ 페이지 및 블록 아카이브/복원 추가
- ✅ 16개 단위 테스트 추가 (100% 통과율)
- ✅ 파일 확장자에서 컨텐츠 타입 자동 감지
- ⚠️ Multipart 업로드 (>20MB) 명확한 오류와 함께 스텁 처리

**v0.1.0 (2026-02-03)**
- 재시도 로직이 있는 초기 구현
- requests.Session을 통한 연결 풀링
- Rate limit 처리 (429)
- 기본 CRUD 작업

## 참고 자료

- [Notion API Reference (2025-09-03)](https://developers.notion.com/reference/intro)
- [File Upload Documentation](https://developers.notion.com/reference/upload-a-file)
- [Data Sources (2025-09-03)](https://developers.notion.com/reference/retrieve-a-data-source)
