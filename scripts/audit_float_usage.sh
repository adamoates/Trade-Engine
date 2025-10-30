#!/bin/bash
# Audit float usage in financial calculations
# This script detects potentially dangerous float usage in trading code

echo "════════════════════════════════════════════════════════════════"
echo "FLOAT USAGE AUDIT - Financial Code Safety Check"
echo "════════════════════════════════════════════════════════════════"
echo ""

FOUND_ISSUES=0

# Directories to check
DIRS="src/trade_engine/domain src/trade_engine/services src/trade_engine/adapters src/trade_engine/core"

echo "🔍 Checking for dangerous float usage patterns..."
echo ""

# Pattern 1: float(price|qty|amount|pnl|...)
echo "1️⃣  Checking for float() conversions on financial values..."
PATTERN1=$(grep -rn "float(.*\(price\|qty\|quantity\|amount\|pnl\|size\|commission\|fee\)\)" $DIRS 2>/dev/null || true)
if [ -n "$PATTERN1" ]; then
    echo "⚠️  FOUND:"
    echo "$PATTERN1"
    echo ""
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "✅ No float() conversions on financial values"
    echo ""
fi

# Pattern 2: Type hints with float for financial fields (improved to catch more cases)
echo "2️⃣  Checking for 'price: float' type hints..."
# Enhanced regex to catch:
# - "price: float" (with space)
# - "price:float" (no space)
# - "price: Optional[float]"
# - "def foo(price: float)"
# - "-> float" in function signatures with financial variable names
PATTERN2=$(grep -rE ":\s*float|:float|:\s*Optional\[float\]|:\s*float\s*\)" $DIRS | grep -iE "(price|qty|quantity|amount|pnl|size|commission|fee|balance|value)" 2>/dev/null || true)
if [ -n "$PATTERN2" ]; then
    echo "⚠️  FOUND:"
    echo "$PATTERN2"
    echo ""
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "✅ No float type hints on financial values"
    echo ""
fi

# Pattern 3: Arithmetic with float literals in financial contexts
echo "3️⃣  Checking for float literals in financial calculations..."
PATTERN3=$(grep -rn "[0-9]\+\.[0-9]\+" $DIRS | grep -v "Decimal(" | grep -E "(price|qty|quantity|amount|pnl|size|commission|fee)" | head -20 2>/dev/null || true)
if [ -n "$PATTERN3" ]; then
    echo "⚠️  FOUND (first 20 matches):"
    echo "$PATTERN3"
    echo ""
    echo "💡 Tip: Use Decimal('0.08') instead of 0.08 for financial values"
    echo ""
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "✅ No float literals in financial calculations"
    echo ""
fi

# Pattern 4: Function signatures with float return types
echo "4️⃣  Checking for '->\s*float' return types in financial functions..."
PATTERN4=$(grep -rE "def\s+\w+.*->\s*float" $DIRS | grep -iE "(price|qty|quantity|amount|pnl|balance|value|calculate|compute)" 2>/dev/null || true)
if [ -n "$PATTERN4" ]; then
    echo "⚠️  FOUND:"
    echo "$PATTERN4"
    echo ""
    echo "💡 Tip: Financial calculation functions should return Decimal, not float"
    echo ""
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "✅ No financial functions returning float"
    echo ""
fi

# Pattern 5: Generic type hints with float (dict[str, float], List[float], etc.)
echo "5️⃣  Checking for generic type hints containing float..."
PATTERN5=$(grep -rE "\[.*float.*\]" $DIRS | grep -iE "(price|qty|quantity|amount|pnl|balance|value)" | grep -v "Decimal" | head -10 2>/dev/null || true)
if [ -n "$PATTERN5" ]; then
    echo "⚠️  FOUND (first 10 matches):"
    echo "$PATTERN5"
    echo ""
    echo "💡 Tip: Use dict[str, Decimal] instead of dict[str, float]"
    echo ""
fi

# Pattern 6: Division that might lose precision
echo "6️⃣  Checking for division in financial code (potential precision loss)..."
PATTERN6=$(grep -rn "/ [0-9]" $DIRS | grep -E "(price|qty|quantity|amount|pnl|size)" | grep -v "Decimal" | head -10 2>/dev/null || true)
if [ -n "$PATTERN6" ]; then
    echo "⚠️  FOUND (first 10 matches - may be false positives):"
    echo "$PATTERN6"
    echo ""
    echo "💡 Tip: Ensure both operands are Decimal for division"
    echo ""
fi

# Positive checks
echo "════════════════════════════════════════════════════════════════"
echo "✅ POSITIVE CHECKS - Correct Decimal Usage"
echo "════════════════════════════════════════════════════════════════"
echo ""

echo "7️⃣  Checking for correct Decimal usage..."
DECIMAL_USAGE=$(grep -rn "from decimal import Decimal" $DIRS 2>/dev/null | wc -l || echo "0")
echo "✅ Files importing Decimal: $DECIMAL_USAGE"
echo ""

echo "8️⃣  Checking for Decimal type hints..."
DECIMAL_HINTS=$(grep -rn ":\s*Decimal" $DIRS 2>/dev/null | wc -l || echo "0")
echo "✅ Decimal type hints found: $DECIMAL_HINTS"
echo ""

# Summary
echo "════════════════════════════════════════════════════════════════"
echo "SUMMARY"
echo "════════════════════════════════════════════════════════════════"
echo ""

if [ $FOUND_ISSUES -eq 0 ]; then
    echo "✅ PASSED - No dangerous float usage detected!"
    echo ""
    echo "Next steps:"
    echo "  1. Add this script to pre-commit hooks"
    echo "  2. Add to CI/CD pipeline"
    echo "  3. Document exceptions (if any)"
    exit 0
else
    echo "⚠️  ISSUES FOUND - $FOUND_ISSUES pattern(s) matched"
    echo ""
    echo "Action required:"
    echo "  1. Review each match above"
    echo "  2. Replace float with Decimal for financial values"
    echo "  3. Re-run this audit"
    echo ""
    echo "Remember: NON-NEGOTIABLE - All financial values must use Decimal"
    exit 1
fi
