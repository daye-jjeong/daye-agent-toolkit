# TDD on New Functions

Write tests before implementation for new functions. Why: writing tests first is NOT over-engineering — it defines the contract before the code exists, catches edge cases the implementation would silently miss, and prevents "simplest approach" from meaning "untested approach."

## Scope

- New exported functions (helpers, utilities, business logic)
- New branches/behaviors on existing functions
- Functions extracted via refactoring

## Process

1. Write a failing test (RED)
2. Minimal implementation to pass (GREEN)
3. Refactor if needed (REFACTOR)

## Exempt

- Simple re-exports, type definitions, constant declarations
- Existing tests already cover the behavior
- Trivial one-liner functions in S-size tasks
