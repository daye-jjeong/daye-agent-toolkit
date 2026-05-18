"""pricing.estimate_cost 단위 테스트.

단가는 Anthropic 공개 리스트가 기준. 단가 변경 시 pricing._RATES와 함께 갱신.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pricing import estimate_cost

M = 1_000_000


def test_opus_input_only():
    # Opus: $15 / 1M input
    assert estimate_cost("claude-opus-4-7", M, 0) == 15.0


def test_opus_output_only():
    # Opus: $75 / 1M output
    assert estimate_cost("claude-opus-4-7", 0, M) == 75.0


def test_sonnet_input_and_output():
    # Sonnet: $3 input + $15 output
    assert estimate_cost("claude-sonnet-4-6", M, M) == 18.0


def test_haiku_input():
    # Haiku: $1 / 1M input
    assert estimate_cost("claude-haiku-4-5-20251001", M, 0) == 1.0


def test_cache_read_is_tenth_of_input():
    # cache read = 0.1x base input → Opus 0.1 * 15 = 1.5
    assert estimate_cost("claude-opus-4-7", 0, 0, cache_read_tokens=M) == 1.5


def test_cache_create_is_1_25x_input():
    # cache write (5m) = 1.25x base input → Opus 1.25 * 15 = 18.75
    assert estimate_cost("claude-opus-4-7", 0, 0, cache_create_tokens=M) == 18.75


def test_unknown_provider_model_returns_zero():
    # Anthropic 모델이 아니면 0 (검증 안 된 수치 박지 않음)
    assert estimate_cost("gpt-4o", M, M) == 0.0


def test_future_opus_version_matches_by_family():
    # 미래 버전도 family substring으로 매칭
    assert estimate_cost("claude-opus-9-9-future", M, 0) == 15.0


def test_empty_model_returns_zero():
    assert estimate_cost("", M, M) == 0.0


def test_zero_tokens_returns_zero():
    assert estimate_cost("claude-opus-4-7", 0, 0) == 0.0


def test_combined_realistic_session():
    # Opus: 50k in, 8k out, 400k cache_read, 30k cache_create
    # = (50000*15 + 8000*75 + 400000*1.5 + 30000*18.75) / 1e6
    expected = (50_000 * 15 + 8_000 * 75 + 400_000 * 1.5 + 30_000 * 18.75) / M
    assert abs(estimate_cost("claude-opus-4-7", 50_000, 8_000,
                             cache_read_tokens=400_000,
                             cache_create_tokens=30_000) - expected) < 1e-9
