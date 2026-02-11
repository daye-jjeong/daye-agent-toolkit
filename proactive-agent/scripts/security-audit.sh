#!/bin/bash
# Proactive Agent Security Audit (clawd adapted)
# Run periodically to check for security issues

set +e

echo "Security Audit"
echo "=================================="
echo ""

ISSUES=0
WARNINGS=0

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

warn() {
    echo -e "${YELLOW}WARNING: $1${NC}"
    ((WARNINGS++))
}

fail() {
    echo -e "${RED}ISSUE: $1${NC}"
    ((ISSUES++))
}

pass() {
    echo -e "${GREEN}OK: $1${NC}"
}

# 1. Check credential file permissions
echo "Checking credential files..."
if [ -d ".credentials" ]; then
    for f in .credentials/*; do
        if [ -f "$f" ]; then
            perms=$(stat -f "%Lp" "$f" 2>/dev/null || stat -c "%a" "$f" 2>/dev/null)
            if [ "$perms" != "600" ]; then
                fail "$f has permissions $perms (should be 600)"
            else
                pass "$f permissions OK (600)"
            fi
        fi
    done
else
    echo "   No .credentials directory found"
fi
echo ""

# 2. Check for exposed secrets
echo "Scanning for exposed secrets..."
SECRET_PATTERNS="(api[_-]?key|apikey|secret|password|token|auth).*[=:].{10,}"
for f in $(ls *.md *.json *.yaml *.yml .env* 2>/dev/null || true); do
    if [ -f "$f" ]; then
        matches=$(grep -iE "$SECRET_PATTERNS" "$f" 2>/dev/null | grep -v "example\|template\|placeholder\|your-\|<\|TODO" || true)
        if [ -n "$matches" ]; then
            warn "Possible secret in $f - review manually"
        fi
    fi
done
pass "Secret scan complete"
echo ""

# 3. Check .gitignore
echo "Checking .gitignore..."
if [ -f ".gitignore" ]; then
    for pattern in ".credentials" ".env" "MEMORY.md" "USER.md" "memory/"; do
        if grep -q "$pattern" ".gitignore"; then
            pass "$pattern is gitignored"
        else
            warn "$pattern may not be gitignored"
        fi
    done
else
    warn "No .gitignore found"
fi
echo ""

# 4. Check AGENTS.md for security rules
echo "Checking AGENTS.md security rules..."
if [ -f "AGENTS.md" ]; then
    if grep -qi "injection\|external content\|never execute" "AGENTS.md"; then
        pass "AGENTS.md contains injection defense rules"
    else
        warn "AGENTS.md may be missing prompt injection defense"
    fi
else
    warn "No AGENTS.md found"
fi
echo ""

# Summary
echo "=================================="
echo "Summary"
echo "=================================="
if [ $ISSUES -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
elif [ $ISSUES -eq 0 ]; then
    echo -e "${YELLOW}$WARNINGS warning(s), 0 issues${NC}"
else
    echo -e "${RED}$ISSUES issue(s), $WARNINGS warning(s)${NC}"
fi
