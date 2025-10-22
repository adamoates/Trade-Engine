#!/bin/bash
# Local CI simulation script
# Runs the same quality checks that GitHub Actions will run
# Run this before pushing to catch issues early

set -e  # Exit on any error

echo "🔍 Running local CI checks (simulating GitHub Actions)..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILED=0

# ============================================================================
# Backend Quality Checks
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Backend Quality Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Black formatting check
echo "🎨 Checking code formatting (Black)..."
if [ -d "engine" ] || [ -d "api" ] || [ -d "scanner" ]; then
    if black --check engine/ api/ scanner/ tests/ 2>/dev/null; then
        echo -e "${GREEN}✅ Black formatting: PASSED${NC}"
    else
        echo -e "${RED}❌ Black formatting: FAILED${NC}"
        echo "   Run: black engine/ api/ scanner/ tests/"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠️  Project directories not yet created - skipping${NC}"
fi
echo ""

# Ruff linting
echo "🔍 Linting code (Ruff)..."
if [ -d "engine" ] || [ -d "api" ] || [ -d "scanner" ]; then
    if ruff check engine/ api/ scanner/ tests/ 2>/dev/null; then
        echo -e "${GREEN}✅ Ruff linting: PASSED${NC}"
    else
        echo -e "${RED}❌ Ruff linting: FAILED${NC}"
        echo "   Fix issues or run: ruff check --fix engine/ api/ scanner/ tests/"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠️  Project directories not yet created - skipping${NC}"
fi
echo ""

# Type checking
echo "🔬 Type checking (mypy)..."
if [ -d "engine" ] || [ -d "api" ]; then
    if mypy engine/ api/ 2>/dev/null; then
        echo -e "${GREEN}✅ Type checking: PASSED${NC}"
    else
        echo -e "${RED}❌ Type checking: FAILED${NC}"
        echo "   Fix type errors in code"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠️  Project directories not yet created - skipping${NC}"
fi
echo ""

# ============================================================================
# Risk-Critical Code Validation
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  Risk-Critical Code Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check for float usage in financial code
echo "💰 Scanning for dangerous float() usage in financial calculations..."
if [ -d "engine" ] || [ -d "api" ]; then
    if grep -r "float(" engine/ api/ 2>/dev/null | grep -E "(price|quantity|pnl|position|balance)"; then
        echo -e "${RED}❌ CRITICAL: Found float() usage in financial code!${NC}"
        echo "   Financial calculations MUST use Decimal, never float"
        FAILED=1
    else
        echo -e "${GREEN}✅ No dangerous float usage detected${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Project directories not yet created - skipping${NC}"
fi
echo ""

# ============================================================================
# Testing
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Running Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if tests exist
if [ -d "tests" ] && [ "$(find tests -name 'test_*.py' -o -name '*_test.py' 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "Running pytest with coverage..."
    if pytest tests/ \
        --cov=engine \
        --cov=api \
        --cov=scanner \
        --cov-report=term-missing \
        --cov-fail-under=80 \
        -v; then
        echo -e "${GREEN}✅ Tests: PASSED${NC}"
    else
        echo -e "${RED}❌ Tests: FAILED${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠️  No tests found yet - this is expected in early phases${NC}"
    echo -e "${YELLOW}   Tests will be required before Phase 2 completion${NC}"
fi
echo ""

# ============================================================================
# Security Scanning
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 Security Scanning"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check for exposed secrets
echo "🕵️  Checking for exposed secrets..."
if git diff --cached --name-only | grep -E '\.env$|credentials|secret|key' >/dev/null; then
    echo -e "${RED}⚠️  WARNING: Potential secret files in commit${NC}"
    echo "   Review: .env, credentials, or key files"
    echo "   These should be in .gitignore"
else
    echo -e "${GREEN}✅ No obvious secrets in commit${NC}"
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ ALL CHECKS PASSED - Ready to push!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Your code meets our 'prove it works' standard."
    echo "GitHub Actions CI will run the same checks when you push."
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ SOME CHECKS FAILED - Do not push yet!${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Fix the issues above before pushing."
    echo "GitHub Actions will reject your code if these checks fail."
    exit 1
fi
