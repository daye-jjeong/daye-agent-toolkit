"""
Session Manager Skill

Provides utilities for spawning and managing subagent sessions with
automatic fallback/retry logic for model selection.
"""

from .spawn_with_fallback import (
    spawn_subagent_with_retry,
    spawn_parallel_workers_with_fallback,
    DEFAULT_FALLBACK_ORDER,
    SpawnError
)

__all__ = [
    'spawn_subagent_with_retry',
    'spawn_parallel_workers_with_fallback',
    'DEFAULT_FALLBACK_ORDER',
    'SpawnError'
]
