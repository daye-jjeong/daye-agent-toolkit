#!/usr/bin/env python3
"""Anthropic API 비용 추정 — 토큰 수 → USD.

단가 출처: Anthropic 공개 리스트가 (https://www.anthropic.com/pricing)
기준일: 2026-05. 단가가 바뀌면 _RATES를 갱신할 것 (검증 안 된 수치 박지 않음).

per-1M-tokens (base input / output):
  opus    15  / 75
  sonnet   3  / 15
  haiku    1  /  5

cache read  = base input x 0.1
cache write = base input x 1.25  (5분 캐시 기준)

매칭: 모델 문자열에 family 키워드(opus/sonnet/haiku)가 들어있으면 해당 단가.
Anthropic 모델이 아니거나 미매칭이면 0.0 (틀린 추정보다 0이 안전).
"""
from __future__ import annotations

_RATES: dict[str, tuple[float, float]] = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}

_CACHE_READ_MULT = 0.1
_CACHE_WRITE_MULT = 1.25
_PER = 1_000_000


def _rate_for(model: str) -> tuple[float, float] | None:
    """모델 문자열에서 family 단가를 찾는다. 미매칭이면 None."""
    if not model:
        return None
    m = model.lower()
    for family, rate in _RATES.items():
        if family in m:
            return rate
    return None


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
) -> float:
    """토큰 수로 API 비용(USD)을 추정. 미지원 모델은 0.0."""
    rate = _rate_for(model)
    if rate is None:
        return 0.0
    in_rate, out_rate = rate
    cost = (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * in_rate * _CACHE_READ_MULT
        + cache_create_tokens * in_rate * _CACHE_WRITE_MULT
    ) / _PER
    return round(cost, 6)
