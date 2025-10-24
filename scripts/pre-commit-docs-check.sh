#!/bin/bash
# Pre-commit hook for documentation validation
# Enforces documentation placement and naming rules

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VIOLATIONS=0

echo "🔍 Validating documentation structure..."

# Get list of staged markdown files
STAGED_MD_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.md$' || true)

if [ -z "$STAGED_MD_FILES" ]; then
    echo -e "${GREEN}✓${NC} No markdown files to validate"
    exit 0
fi

# Allowed files in project root
ALLOWED_ROOT_FILES=(
    "README.md"
    "ROADMAP.md"
    "CLAUDE.md"
    "CHANGELOG.md"
    "LICENSE.md"
    "DOCUMENT_PLACEMENT_RULES.md"
)

# Valid documentation categories
VALID_CATEGORIES=(
    "guides"
    "reference"
    "reports"
    "troubleshooting"
    "architecture"
    "archive"
)

# Function to check if string is in array
contains() {
    local seeking=$1; shift
    local in=1
    for element; do
        if [[ "$element" == "$seeking" ]]; then
            in=0
            break
        fi
    done
    return $in
}

# Function to check kebab-case
is_kebab_case() {
    local filename=$1
    # Kebab-case: lowercase, hyphens only, no underscores, no spaces
    if [[ "$filename" =~ ^[a-z0-9]+(-[a-z0-9]+)*\.md$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to check metadata header
check_metadata() {
    local file=$1

    if [ ! -f "$file" ]; then
        return 1
    fi

    # Check for required metadata fields
    local has_last_updated=$(grep -c "^\*\*Last Updated\*\*:" "$file" || echo 0)
    local has_category=$(grep -c "^\*\*Category\*\*:" "$file" || echo 0)
    local has_status=$(grep -c "^\*\*Status\*\*:" "$file" || echo 0)

    if [ "$has_last_updated" -eq 0 ] || [ "$has_category" -eq 0 ] || [ "$has_status" -eq 0 ]; then
        return 1
    fi

    return 0
}

echo ""
echo "Checking staged markdown files:"
echo "--------------------------------"

for file in $STAGED_MD_FILES; do
    filename=$(basename "$file")
    dirname=$(dirname "$file")

    # Skip deleted files
    if [ ! -f "$file" ]; then
        continue
    fi

    echo -n "  $file ... "

    # Check 1: Files in project root
    if [[ "$dirname" == "." ]]; then
        if contains "$filename" "${ALLOWED_ROOT_FILES[@]}"; then
            echo -e "${GREEN}✓${NC} (allowed root file)"
            continue
        else
            echo -e "${RED}✗${NC} Prohibited file in project root"
            echo -e "    ${YELLOW}→${NC} Only these files allowed in root: ${ALLOWED_ROOT_FILES[*]}"
            VIOLATIONS=$((VIOLATIONS + 1))
            continue
        fi
    fi

    # Check 2: Files in docs/ root (only README.md allowed)
    if [[ "$dirname" == "docs" ]]; then
        if [[ "$filename" == "README.md" ]]; then
            echo -e "${GREEN}✓${NC} (docs index)"
            continue
        else
            echo -e "${RED}✗${NC} Prohibited file in docs/ root"
            echo -e "    ${YELLOW}→${NC} Files must be in category subdirectories: docs/{${VALID_CATEGORIES[*]}}"
            echo -e "    ${YELLOW}→${NC} Use: docs/guides/, docs/reference/, docs/reports/, etc."
            VIOLATIONS=$((VIOLATIONS + 1))
            continue
        fi
    fi

    # Check 3: Files must be in valid category
    if [[ "$dirname" =~ ^docs/([^/]+) ]]; then
        category="${BASH_REMATCH[1]}"

        if ! contains "$category" "${VALID_CATEGORIES[@]}"; then
            echo -e "${RED}✗${NC} Invalid category: $category"
            echo -e "    ${YELLOW}→${NC} Valid categories: ${VALID_CATEGORIES[*]}"
            VIOLATIONS=$((VIOLATIONS + 1))
            continue
        fi
    elif [[ "$dirname" =~ ^docs/ ]]; then
        echo -e "${RED}✗${NC} File not in valid category"
        echo -e "    ${YELLOW}→${NC} Must be in: docs/{${VALID_CATEGORIES[*]}}"
        VIOLATIONS=$((VIOLATIONS + 1))
        continue
    fi

    # Check 4: Kebab-case naming (except special files)
    if [[ "$filename" != "README.md" ]]; then
        if ! is_kebab_case "$filename"; then
            echo -e "${RED}✗${NC} Invalid filename (not kebab-case)"
            echo -e "    ${YELLOW}→${NC} Use lowercase with hyphens: my-document-name.md"
            echo -e "    ${YELLOW}→${NC} Not: MyDocument.md, my_document.md, or My Document.md"
            VIOLATIONS=$((VIOLATIONS + 1))
            continue
        fi
    fi

    # Check 5: Metadata header (for categorized docs)
    if [[ "$dirname" =~ ^docs/(guides|reference|reports|troubleshooting|architecture) ]]; then
        if ! check_metadata "$file"; then
            echo -e "${YELLOW}⚠${NC}  Missing metadata header"
            echo -e "    ${YELLOW}→${NC} Add to top of file:"
            echo -e "       # Document Title"
            echo -e "       **Last Updated**: YYYY-MM-DD"
            echo -e "       **Category**: $category"
            echo -e "       **Status**: active"
            # Warning only, not a hard failure
            # VIOLATIONS=$((VIOLATIONS + 1))
            continue
        fi
    fi

    echo -e "${GREEN}✓${NC}"
done

# Check if docs/README.md was updated when new docs added
NEW_DOCS=$(echo "$STAGED_MD_FILES" | grep -v "docs/README.md" | grep "^docs/" || true)
README_UPDATED=$(echo "$STAGED_MD_FILES" | grep "docs/README.md" || true)

if [ -n "$NEW_DOCS" ] && [ -z "$README_UPDATED" ]; then
    echo ""
    echo -e "${YELLOW}⚠${NC}  Warning: New documentation added but docs/README.md not updated"
    echo -e "    ${YELLOW}→${NC} Consider updating the master index: docs/README.md"
    echo ""
    # Warning only, not blocking
fi

echo ""
echo "================================"

if [ $VIOLATIONS -gt 0 ]; then
    echo -e "${RED}✗ Found $VIOLATIONS violation(s)${NC}"
    echo ""
    echo "Documentation rules enforce:"
    echo "  1. Files in project root must be one of: ${ALLOWED_ROOT_FILES[*]}"
    echo "  2. Files in docs/ root must be README.md only"
    echo "  3. All other docs must be in: docs/{${VALID_CATEGORIES[*]}}"
    echo "  4. Filenames must use kebab-case: my-document.md"
    echo "  5. Categorized docs should have metadata headers"
    echo ""
    echo "See DOCUMENT_PLACEMENT_RULES.md for complete rules and examples"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ All documentation checks passed${NC}"
echo ""
exit 0
