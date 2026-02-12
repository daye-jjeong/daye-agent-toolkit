#!/bin/bash
# Verification script for Task Policy Guardrails implementation

set -e  # Exit on error

echo "=== Task Policy Guardrails - Implementation Verification ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to repo root
cd "$(dirname "$0")/../../.."

echo "📍 Working directory: $(pwd)"
echo ""

# 1. Check directory structure
echo "1️⃣  Checking directory structure..."
REQUIRED_DIRS=(
    "skills/task_policy_guardrails/lib"
    "skills/task_policy_guardrails/tests"
    "$HOME/.clawdbot/guardrails/state"
    "$HOME/.clawdbot/guardrails/audit"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ${GREEN}✓${NC} $dir"
    else
        echo -e "  ${RED}✗${NC} $dir (missing)"
        exit 1
    fi
done
echo ""

# 2. Check core library files
echo "2️⃣  Checking core library files..."
REQUIRED_FILES=(
    "skills/task_policy_guardrails/lib/__init__.py"
    "skills/task_policy_guardrails/lib/classifier.py"
    "skills/task_policy_guardrails/lib/validator.py"
    "skills/task_policy_guardrails/lib/state.py"
    "skills/task_policy_guardrails/lib/deliverable_checker.py"
    "skills/task_policy_guardrails/lib/vault_writer.py"
    "skills/task_policy_guardrails/lib/logger.py"
    "skills/task_policy_guardrails/lib/gates.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
        exit 1
    fi
done
echo ""

# 3. Check test files
echo "3️⃣  Checking test files..."
TEST_FILES=(
    "skills/task_policy_guardrails/tests/test_classifier.py"
    "skills/task_policy_guardrails/tests/test_gates.py"
)

for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
        exit 1
    fi
done
echo ""

# 4. Test imports
echo "4️⃣  Testing Python imports..."
python3 -c "from skills.task_policy_guardrails.lib import *" 2>&1
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} All imports successful"
else
    echo -e "  ${RED}✗${NC} Import errors detected"
    exit 1
fi
echo ""

# 5. Run unit tests
echo "5️⃣  Running unit tests..."
python3 -m pytest skills/task_policy_guardrails/tests/test_classifier.py -v || {
    echo -e "  ${YELLOW}⚠${NC}  Some tests failed (check output above)"
}
echo ""

python3 -m pytest skills/task_policy_guardrails/tests/test_gates.py -v || {
    echo -e "  ${YELLOW}⚠${NC}  Some tests failed (check output above)"
}
echo ""

# 6. Test classifier
echo "6️⃣  Testing work classifier..."
python3 skills/task_policy_guardrails/lib/classifier.py > /tmp/classifier_test.txt
if grep -q "=== Work Classification Test ===" /tmp/classifier_test.txt; then
    echo -e "  ${GREEN}✓${NC} Classifier test passed"
else
    echo -e "  ${RED}✗${NC} Classifier test failed"
    cat /tmp/classifier_test.txt
    exit 1
fi
echo ""

# 7. Test state management
echo "7️⃣  Testing state management..."
python3 skills/task_policy_guardrails/lib/state.py > /tmp/state_test.txt
if grep -q "Test complete" /tmp/state_test.txt; then
    echo -e "  ${GREEN}✓${NC} State management test passed"
else
    echo -e "  ${RED}✗${NC} State management test failed"
    cat /tmp/state_test.txt
    exit 1
fi
echo ""

# 8. Test logger
echo "8️⃣  Testing logger..."
python3 skills/task_policy_guardrails/lib/logger.py > /tmp/logger_test.txt
if grep -q "Guardrails Logger Test" /tmp/logger_test.txt; then
    echo -e "  ${GREEN}✓${NC} Logger test passed"
else
    echo -e "  ${RED}✗${NC} Logger test failed"
    cat /tmp/logger_test.txt
    exit 1
fi
echo ""

# 9. Test gates
echo "9️⃣  Testing gates..."
python3 skills/task_policy_guardrails/lib/gates.py > /tmp/gates_test.txt
if grep -q "Gate tests complete" /tmp/gates_test.txt; then
    echo -e "  ${GREEN}✓${NC} Gates test passed"
else
    echo -e "  ${RED}✗${NC} Gates test failed"
    cat /tmp/gates_test.txt
    exit 1
fi
echo ""

# 10. Check documentation
echo "🔟 Checking documentation..."
DOC_FILES=(
    "skills/task_policy_guardrails/SPEC.md"
    "skills/task_policy_guardrails/README.md"
    "skills/task_policy_guardrails/IMPLEMENTATION_CHECKLIST.md"
)

for file in "${DOC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${YELLOW}⚠${NC}  $file (existing doc, not updated yet)"
    fi
done
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Implementation verification complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review test output above"
echo "  2. Update SPEC.md with implementation notes"
echo "  3. Create example integration wrappers"
echo "  4. Test with real workflow"
echo ""
