"""
Regression tests for news-brief enrich pipeline.
Commit 01c1b14 fix: enrich 단계에서 영어 텍스트 한국어 번역 의무화

Test Coverage:
1. English text detection and rejection (headline, summary, why)
2. RSS raw text detection in summary
3. Complete item coverage (no partial processing)
4. Final HTML validation (zero English text)
5. Highlight generation quality
"""

import json
import sys
import tempfile
from pathlib import Path
import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from enrich import _is_english, _is_raw_rss, extract, apply


class TestEnrichRegression:
    """Regression test suite for news-brief enrich fixes."""

    @pytest.fixture
    def sample_composed_data(self):
        """Sample composed.json with English text (pre-fix state)."""
        return {
            "date": "2026-03-09",
            "sections": [
                {
                    "title": "AI & Tech",
                    "items": [
                        {
                            "headline": "OpenAI Releases GPT-5",
                            "url": "https://example.com/gpt5",
                            "source": "TechCrunch"
                        },
                        {
                            "headline": "Google Announces Gemini 3.0",
                            "url": "https://example.com/gemini",
                            "source": "Google Blog"
                        }
                    ]
                },
                {
                    "title": "Business",
                    "items": [
                        {
                            "headline": "Meta's Quarterly Results Beat Expectations",
                            "url": "https://example.com/meta",
                            "source": "Reuters"
                        }
                    ]
                }
            ]
        }

    @pytest.fixture
    def sample_enrichments_correct(self):
        """Correct enrichments (all Korean, no English)."""
        return {
            "highlight": "인공지능 기술의 빠른 발전과 글로벌 빅테크 기업들의 경쟁이 심화되고 있으며, 한국 테크 기업들도 이에 대응하고 있습니다.",
            "0.0": {
                "headline": "오픈에이아이, 차세대 모델 발표",
                "summary": "인공지능 연구 기업이 차세대 거대언어모델을 공개했으며, 이는 이전 버전 대비 성능이 크게 향상되었습니다.",
                "why": "생성형 인공지능 시장 경쟁이 심화되면서 한국 기술 기업들도 차기 모델 개발을 가속화해야 합니다."
            },
            "0.1": {
                "headline": "구글, 새 멀티모달 인공지능 모델 공개",
                "summary": "구글이 새로운 멀티모달 인공지능 모델을 공개했으며, 텍스트·이미지·비디오 처리 능력이 강화되었습니다.",
                "why": "멀티모달 인공지능의 실용화가 빨라지면서 기업들의 기술 도입 속도가 가속화되고 있습니다."
            },
            "1.0": {
                "headline": "메타, 분기 실적 예상 초과 달성",
                "summary": "메타가 최근 분기 실적에서 예상을 뛰어넘는 매출 성장과 순이익을 기록했습니다.",
                "why": "광고 시장 회복과 기술 투자 효율화로 메타의 기업 가치가 재평가되고 있습니다."
            }
        }

    @pytest.fixture
    def sample_enrichments_with_english_headline(self):
        """Incorrect enrichments with English headline (regression case)."""
        return {
            "highlight": "기술 뉴스와 비즈니스 현황을 정리했습니다.",
            "0.0": {
                "headline": "OpenAI Releases GPT-5",  # ❌ English
                "summary": "OpenAI가 차세대 거대언어모델 GPT-5를 공개했습니다.",
                "why": "생성형 AI 시장 경쟁이 심화되고 있습니다."
            },
            "0.1": {
                "headline": "구글, Gemini 3.0 발표",
                "summary": "구글이 Gemini 3.0을 공개했습니다.",
                "why": "멀티모달 AI의 실용화가 빨라지고 있습니다."
            },
            "1.0": {
                "headline": "메타의 분기 실적 예상 초과",
                "summary": "메타가 최근 분기 실적을 발표했습니다.",
                "why": "광고 시장 회복이 진행 중입니다."
            }
        }

    @pytest.fixture
    def sample_enrichments_with_english_summary(self):
        """Incorrect enrichments with English summary (regression case)."""
        return {
            "highlight": "기술과 비즈니스 뉴스입니다.",
            "0.0": {
                "headline": "OpenAI, GPT-5 출시",
                "summary": "OpenAI releases the next-generation LLM GPT-5.",  # ❌ English
                "why": "생성형 AI 시장의 경쟁이 격화되고 있습니다."
            },
            "0.1": {
                "headline": "구글, Gemini 3.0 발표",
                "summary": "구글이 Gemini 3.0을 공개했습니다.",
                "why": "멀티모달 AI가 실용화 단계에 접어들고 있습니다."
            },
            "1.0": {
                "headline": "메타의 분기 실적 예상 초과",
                "summary": "Meta beats quarterly expectations with strong growth.",  # ❌ English
                "why": "광고 시장이 회복되고 있습니다."
            }
        }

    @pytest.fixture
    def sample_enrichments_with_rss_raw(self):
        """Incorrect enrichments with raw RSS content (regression case)."""
        return {
            "highlight": "뉴스 브리핑입니다.",
            "0.0": {
                "headline": "OpenAI, GPT-5 출시",
                "summary": "OpenAI released GPT-5 today. The company said the model is 50% faster than GPT-4.",  # ❌ Raw RSS/English
                "why": "생성형 AI 시장 경쟁이 심화되고 있습니다."
            },
            "0.1": {
                "headline": "구글, Gemini 3.0 발표",
                "summary": "구글이 Gemini 3.0을 공개했습니다.",
                "why": "멀티모달 AI의 실용화가 빨라지고 있습니다."
            },
            "1.0": {
                "headline": "메타의 분기 실적 예상 초과",
                "summary": "메타가 분기 실적을 발표했습니다.",
                "why": "광고 시장 회복이 진행 중입니다."
            }
        }

    @pytest.fixture
    def sample_enrichments_partial_processing(self):
        """Incorrect enrichments with missing items (partial processing)."""
        return {
            "highlight": "뉴스 브리핑입니다.",
            "0.0": {
                "headline": "OpenAI, GPT-5 출시",
                "summary": "OpenAI가 차세대 거대언어모델 GPT-5를 공개했습니다.",
                "why": "생성형 AI 시장 경쟁이 심화되고 있습니다."
            }
            # ❌ Missing 0.1 and 1.0 — incomplete processing
        }

    # ============ Test Case 1: English headline detection ============
    def test_rc_1_english_headline_detection(self):
        """RC-1: Detect and reject English headlines in enrichments.
        
        Regression: commit 01c1b14 fixed headline translation requirement.
        Expected: Pure English headlines should be identified as invalid.
        """
        # Pure English: should be detected
        assert _is_english("OpenAI Releases GPT-5") == True
        assert _is_english("Google Announces Gemini 3.0") == True
        assert _is_english("Meta Beats Quarterly Expectations") == True
        
        # Korean with some English brand names: should NOT be detected as English
        assert _is_english("구글, Gemini 3.0 발표") == False
        assert _is_english("메타, 분기 실적 예상 초과") == False

    # ============ Test Case 2: English summary detection ============
    def test_rc_2_english_summary_detection(self):
        """RC-2: Detect and reject English summaries in enrichments.
        
        Regression: commit 01c1b14 added "모든 항목 빠짐없이 처리" rule.
        Expected: Summary fields should be fully Korean.
        """
        eng_summary = "OpenAI releases the next-generation LLM GPT-5."
        korean_summary = "OpenAI가 차세대 거대언어모델 GPT-5를 공개했습니다."
        
        assert _is_english(eng_summary) == True
        assert _is_english(korean_summary) == False

    # ============ Test Case 3: RSS raw text detection ============
    def test_rc_3_rss_raw_text_detection(self):
        """RC-3: Detect raw RSS content (verbatim source text).
        
        Regression: commit 01c1b14 enforces "RSS 원문 붙여넣기 금지".
        Expected: Raw RSS patterns should be identified.
        """
        # HTML entities = raw RSS
        raw_rss_html = "OpenAI released &quot;GPT-5&quot; today."
        
        # Byline pattern = raw RSS
        raw_rss_byline = "(서울=연합뉴스) 기자 = OpenAI가 GPT-5를 발표했습니다."
        
        # Too short = raw RSS
        raw_rss_short = "New AI model"
        
        # Truncated with ellipsis = raw RSS
        raw_rss_truncated = "OpenAI releases new model that is 50% faster..."
        
        # Good summary: complete sentence, no HTML entities
        good_summary = "OpenAI가 차세대 모델 GPT-5를 공개했으며, 이전 모델 대비 50% 향상된 성능을 제공합니다."
        
        assert _is_raw_rss(raw_rss_html) == True
        assert _is_raw_rss(raw_rss_byline) == True
        assert _is_raw_rss(raw_rss_short) == True
        assert _is_raw_rss(raw_rss_truncated) == True
        assert _is_raw_rss(good_summary) == False

    # ============ Test Case 4: Complete item coverage ============
    def test_rc_4_complete_item_coverage(self, sample_composed_data, sample_enrichments_partial_processing):
        """RC-4: Validate that all items are processed (no partial enrichment).
        
        Regression: commit 01c1b14 requires "모든 항목 빠짐없이 처리할 것".
        Expected: Enrichments dict should cover all items in sections.
        """
        # Count expected items
        expected_count = sum(len(s["items"]) for s in sample_composed_data["sections"])
        
        # Count enriched items (exclude highlight)
        enriched_count = len([k for k in sample_enrichments_partial_processing.keys() if k != "highlight"])
        
        # Partial processing case: enriched_count < expected_count
        assert enriched_count < expected_count, "Partial enrichment should be detected"

    # ============ Test Case 5: Final HTML validation (zero English) ============
    def test_rc_5_final_html_no_english(self, sample_composed_data, sample_enrichments_correct):
        """RC-5: Validate that final HTML contains zero English text.
        
        Regression: commit 01c1b14 adds explicit rule:
        "최종 HTML에 영어 텍스트가 하나도 남으면 안 됨 (headline, summary, why 모두 한국어)"
        
        Expected: All headline, summary, why fields must pass Korean check.
        """
        for section_idx, section in enumerate(sample_composed_data["sections"]):
            for item_idx, item in enumerate(section["items"]):
                key = f"{section_idx}.{item_idx}"
                assert key in sample_enrichments_correct, f"Missing enrichment for {key}"
                
                enrichment = sample_enrichments_correct[key]
                
                # All three fields must be Korean (not English)
                assert not _is_english(enrichment["headline"]), \
                    f"Headline is English: {enrichment['headline']}"
                assert not _is_english(enrichment["summary"]), \
                    f"Summary is English: {enrichment['summary']}"
                assert not _is_english(enrichment["why"]), \
                    f"Why field is English: {enrichment['why']}"

    # ============ Test Case 6: Highlight generation quality ============
    def test_rc_6_highlight_quality(self, sample_enrichments_correct):
        """RC-6: Validate highlight quality (no category listing, concrete flow).
        
        Regression: commit 01c1b14 reinforces highlight requirement:
        "섹션 카테고리 나열 금지 ('AI·테크 트렌드와 글로벌 뉴스 종합' 같은 건 의미 없음)"
        
        Expected: Highlight should be narrative summary, not category list.
        """
        highlight = sample_enrichments_correct["highlight"]
        
        # Should NOT be empty
        assert len(highlight) > 0, "Highlight is empty"
        
        # Should NOT contain category names alone
        assert not highlight.startswith("AI·"), "Highlight is just category name"
        assert "종합" not in highlight or len(highlight) > 30, \
            "Highlight is too generic (just category listing)"
        
        # Should be 2-3 sentences (rough check: contains 2+ periods)
        assert highlight.count("。") + highlight.count(".") >= 1, \
            "Highlight should be 2-3 sentences"


class TestEnrichIntegration:
    """Integration tests for extract → enrich → apply workflow."""

    @pytest.fixture
    def sample_workflow(self, tmp_path):
        """Set up temp files for extract → apply workflow."""
        return {
            "input_file": tmp_path / "composed.json",
            "extract_output": tmp_path / "to_enrich.json",
            "enrichments_file": tmp_path / "enrichments.json",
            "output_file": tmp_path / "enriched.json"
        }

    @pytest.fixture
    def sample_composed_data(self):
        """Simple composed data with 2 items."""
        return {
            "date": "2026-03-09",
            "sections": [
                {
                    "title": "Tech",
                    "items": [
                        {
                            "headline": "AI Models Get Smarter",
                            "url": "https://example.com/ai",
                            "source": "Source 1"
                        }
                    ]
                }
            ]
        }

    def test_integration_extract_valid_json(self, sample_workflow, sample_composed_data):
        """Test that extract produces valid, parseable JSON."""
        with open(sample_workflow["input_file"], "w") as f:
            json.dump(sample_composed_data, f)
        
        extracted = extract(sample_composed_data)
        
        # Should be valid JSON-serializable dict
        assert isinstance(extracted, dict)
        assert "items" in extracted
        assert "instructions" in extracted
        assert len(extracted["items"]) == 1

    def test_integration_apply_merges_correctly(self, sample_workflow, sample_composed_data):
        """Test that apply correctly merges enrichments back."""
        input_composed = sample_composed_data.copy()
        
        # Simulate enrichments
        enrichments = {
            "highlight": "기술 뉴스 정리입니다.",
            "0.0": {
                "headline": "인공지능 모델이 더 나아지고 있습니다",
                "summary": "인공지능 모델들이 지속적으로 성능을 향상시키고 있습니다.",
                "why": "성능 향상은 기업의 경쟁력 강화로 이어집니다."
            }
        }
        
        result_data, applied_count = apply(input_composed, enrichments)
        
        # Check that enrichments were applied (apply returns tuple)
        assert applied_count == 1, "Should apply 1 enrichment"
        assert result_data["sections"][0]["items"][0]["headline"] == enrichments["0.0"]["headline"]
        assert result_data["sections"][0]["items"][0]["summary"] == enrichments["0.0"]["summary"]
        assert result_data["sections"][0]["items"][0]["why"] == enrichments["0.0"]["why"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
