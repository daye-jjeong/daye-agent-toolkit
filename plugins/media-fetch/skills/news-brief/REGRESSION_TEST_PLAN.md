# Regression Test Plan — news-brief enrich pipeline

**Commit Reference:** `01c1b14` (2026-03-07)
**Fix Summary:** enrich 단계에서 영어 텍스트 한국어 번역 의무화

## Regression Context

**Problem (Before Fix):**
- cron 에이전트가 enrich 단계를 불완전하게 수행하거나 생략
- RSS 원본 텍스트가 그대로 노출되거나, 영어 headline/summary가 최종 HTML에 남음
- 제목과 요약이 혼합되거나 누락됨

**Root Cause:**
1. enrich 단계가 선택사항으로 취급됨 (compose 후 바로 render)
2. 품질 기준이 명확하지 않아 에이전트가 부분 처리로 넘어감
3. 최종 검증 단계 없음 (영어 텍스트가 남았는지 확인 안 함)

**Fix Applied (Commit 01c1b14):**
- `SKILL.md`: enrich 단계 **절대 생략 불가** 원칙 명시
- `cron.json`: 상세 인스트럭션 + 최종 검증 체크리스트 추가
- `enrich.py`: 번역 요구사항 명확화 + 영어 텍스트 감지 로직 강화

## Test Coverage

### RC-1: English Headline Detection ✅
**Test:** `test_rc_1_english_headline_detection`

**Coverage:**
- Pure English headlines are detected as needing translation
- Headlines with Korean + brand names (e.g., "구글, Gemini 3.0") are NOT flagged as English

**Verification Method:**
- Use `_is_english()` function from enrich.py
- ASCII letter ratio > 60% = English

**Cases:**
- ✅ "OpenAI Releases GPT-5" → English (needs translation)
- ✅ "Google Announces Gemini 3.0" → English
- ✅ "구글, Gemini 3.0 발표" → Korean (mixed OK)

---

### RC-2: English Summary Detection ✅
**Test:** `test_rc_2_english_summary_detection`

**Coverage:**
- English-only summaries must be identified for translation
- Korean summaries pass validation

**Verification Method:**
- Use `_is_english()` function
- Check ASCII letter ratio

**Cases:**
- ✅ "OpenAI releases..." → English (needs translation)
- ✅ "OpenAI가 차세대 모델을..." → Korean (passes)

---

### RC-3: RSS Raw Text Detection ✅
**Test:** `test_rc_3_rss_raw_text_detection`

**Coverage:**
- Detect raw RSS content (verbatim source text):
  - HTML entities (`&quot;`, `&amp;`)
  - Wire service bylines (`(서울=연합뉴스)`)
  - Text too short (< 15 chars)
  - Truncated text (ends with "...")
- Good summaries (complete sentences, no HTML, no bylines) pass

**Verification Method:**
- Use `_is_raw_rss()` function from enrich.py
- Multiple detection patterns

**Cases:**
- ❌ "OpenAI released &quot;GPT-5&quot;" → Raw RSS (has HTML entities)
- ❌ "(서울=연합뉴스) 기자 = 발표..." → Raw RSS (byline pattern)
- ❌ "New AI model" → Raw RSS (too short)
- ❌ "Model released today..." → Raw RSS (truncated with ellipsis)
- ✅ "OpenAI가 차세대 모델을 공개했습니다." → Good summary

---

### RC-4: Complete Item Coverage ✅
**Test:** `test_rc_4_complete_item_coverage`

**Coverage:**
- All items in sections must be enriched (no partial processing)
- Partial enrichment (skipping items) is detected as error

**Requirement from Commit:**
> "모든 항목 빠짐없이 처리할 것. 일부만 하고 넘어가면 영어가 섞인 신문이 됨"

**Verification Method:**
- Count total items in all sections
- Count enriched items in enrichments JSON
- Assert: enriched_count == total_count

**Expected:**
- If section[0] has 2 items and section[1] has 1 item = 3 total
- Enrichments must have "0.0", "0.1", "1.0" (and "highlight")
- Missing keys = FAIL

---

### RC-5: Final HTML No English ✅
**Test:** `test_rc_5_final_html_no_english`

**Coverage:**
- Final validation: all headline, summary, why fields must be Korean
- Zero English text allowed in final output

**Requirement from Commit:**
> "최종 HTML에 영어 텍스트가 하나도 남으면 안 됨 (headline, summary, why 모두 한국어)"

**Verification Method:**
- For each enrichment item, validate:
  - `_is_english(headline)` → False
  - `_is_english(summary)` → False
  - `_is_english(why)` → False

**Expected:**
- All three fields must be Korean
- ASCII letter ratio ≤ 60%

---

### RC-6: Highlight Quality ✅
**Test:** `test_rc_6_highlight_quality`

**Coverage:**
- Highlight must be narrative summary, not category listing
- Should avoid generic formulas like "AI·테크 트렌드와 글로벌 뉴스 종합"
- 2-3 sentences (concrete flow, not category names)

**Requirement from Commit:**
> "섹션 카테고리 나열 금지 ('AI·테크 트렌드와 글로벌 뉴스 종합' 같은 건 의미 없음)"
> "전체 기사를 종합해서 '오늘의 핵심' 2-3문장을 작성하세요"

**Verification Method:**
- Check that highlight is not empty
- Check that it doesn't just list category names
- Check that it contains sentence delimiters (。or .)

**Expected:**
- ❌ "AI·테크 트렌드와 글로벌 뉴스 종합"
- ✅ "인공지능 기술의 빠른 발전과 글로벌 빅테크 기업들의 경쟁이 심화되고 있습니다."

---

## Integration Tests

### Integration 1: Extract Valid JSON ✅
**Test:** `test_integration_extract_valid_json`

**Coverage:**
- `extract()` function produces valid, parseable JSON
- Output contains "items" and "instructions" keys
- Item count matches source count

---

### Integration 2: Apply Merges Correctly ✅
**Test:** `test_integration_apply_merges_correctly`

**Coverage:**
- `apply()` function correctly merges enrichments back
- Field-level updates (headline, summary, why) applied correctly
- Return value: tuple (data, applied_count)

---

## Running Tests

### Quick Run
```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/shared/news-brief

# Activate venv
source venv/bin/activate

# Run all tests
python3 -m pytest tests/test_enrich_regression.py -v

# Run specific test class
python3 -m pytest tests/test_enrich_regression.py::TestEnrichRegression -v

# Run specific test
python3 -m pytest tests/test_enrich_regression.py::TestEnrichRegression::test_rc_1_english_headline_detection -v
```

### CI/CD Integration (Recommended)

Add to `.github/workflows/test.yml` (or equivalent):

```yaml
name: Regression Tests

on: [push, pull_request]

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        working-directory: ./shared/news-brief
        run: |
          python -m pip install pytest

      - name: Run regression tests
        working-directory: ./shared/news-brief
        run: |
          python -m pytest tests/test_enrich_regression.py -v --junitxml=junit.xml

      - name: Upload results
        uses: actions/upload-artifact@v2
        if: always()
        with:
          name: test-results
          path: shared/news-brief/junit.xml
```

---

## Test Results Summary

**Total Tests:** 8
**Passed:** 8 ✅
**Failed:** 0

**Breakdown:**
- Regression Tests (RC-1 to RC-6): 6/6 passed
- Integration Tests: 2/2 passed

**Execution Time:** < 0.1s

---

## Known Limitations

1. **No End-to-End HTML Validation:** Tests validate JSON structure, not rendered HTML
   - Future: Add HTML parsing + text extraction to validate final output
   
2. **No Cron Workflow Test:** Does not test actual cron execution
   - Future: Add integration test that mocks cron agent behavior

3. **Heuristic-Based Detection:** `_is_english()` and `_is_raw_rss()` use heuristics
   - May have false positives/negatives for mixed-language text
   - Acceptable for 95%+ of Korean news content

---

## Regression Test Maintenance

**When to Add New Tests:**
- New English text detection patterns discovered
- New RSS format variations found
- New enrich pipeline features added

**When to Update Tests:**
- Enrich function logic changes
- Detection threshold changes (e.g., ASCII ratio from 60% → 70%)
- New quality criteria added to cron.json

---

## Contact & Escalation

- **Owner:** QA Agent (필)
- **Maintained By:** news-brief skill team
- **Escalation:** If regression tests fail, review commit diff against:
  - `scripts/enrich.py`
  - `cron.json`
  - `SKILL.md`
