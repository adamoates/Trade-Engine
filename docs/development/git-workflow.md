# Git Workflow Guide

## 🎯 Workflow Philosophy

This project uses a **trunk-based development** approach with feature branches and strict quality gates.

### Core Principles
1. **Main is always deployable** - Never push broken code to main
2. **Small, incremental changes** - PRs should be reviewable in <30 minutes
3. **Test before merge** - 100% test pass rate required
4. **Document as you go** - Update CHANGELOG.md with every meaningful change

## 📋 Branch Strategy

### Branch Naming Convention

```
<type>/<short-description>

Types:
- feature/    - New functionality
- fix/        - Bug fixes
- refactor/   - Code restructuring (no functionality change)
- docs/       - Documentation updates
- test/       - Test additions or modifications
- chore/      - Build/tooling changes
```

**Examples:**
```bash
feature/add-l2-orderbook-feed
fix/risk-manager-midnight-bug
refactor/backend-structure
docs/update-deployment-guide
test/add-broker-integration-tests
chore/update-ci-coverage-threshold
```

### Branch Lifecycle

```
1. Create branch from main
   ↓
2. Make changes + commit
   ↓
3. Push to remote
   ↓
4. Create PR
   ↓
5. CI checks pass
   ↓
6. Review + approval
   ↓
7. Squash merge to main
   ↓
8. Delete feature branch
```

## 🛠️ Development Workflow

### 1. Start New Work

```bash
# Update main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/my-new-feature

# Verify clean state
git status
```

### 2. Make Changes

```bash
# Make your code changes
# Write tests for new functionality
# Run tests locally
pytest

# Check code quality
black src/ tests/
ruff check src/ tests/
```

### 3. Commit Changes

**Commit Message Format:**
```
<type>: <short summary> (max 72 chars)

<optional detailed description>

<optional footer: references, breaking changes>
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`

**Examples:**
```bash
# Feature commit
git commit -m "feat: Add L2 order book imbalance strategy

Implements bid/ask volume ratio calculation with configurable
thresholds (default: 3.0x buy, 0.33x sell).

Tests: 23 new tests, 97% coverage"

# Bug fix commit
git commit -m "fix: Correct midnight datetime wrap-around in RiskManager

Previous implementation failed to reset daily counters at midnight
when using naive datetime. Now uses timezone-aware datetime.

Fixes: Risk limits not resetting at day boundary"

# Refactor commit
git commit -m "refactor: Extract broker base interface

Created BrokerAdapter ABC to enforce consistent interface across
all broker implementations. No functionality changes."

# Documentation commit
git commit -m "docs: Add git workflow guide

Created comprehensive guide in docs/guides/git-workflow.md covering
branch strategy, commit conventions, and PR process."
```

### 4. Push to Remote

```bash
# First push (creates remote branch)
git push -u origin feature/my-new-feature

# Subsequent pushes
git push
```

### 5. Create Pull Request

**Via GitHub CLI:**
```bash
gh pr create \
  --title "feat: Add L2 order book imbalance strategy" \
  --body "$(cat <<'EOF'
## Summary
Implements L2 order book imbalance detection for generating trading signals.

## Changes
- New L2ImbalanceStrategy class
- Binance L2 data feed adapter
- 23 comprehensive tests (97% coverage)

## Testing
```bash
pytest tests/unit/test_alpha_l2_imbalance.py -v
```

## Checklist
- [x] Tests passing (465/465)
- [x] Code formatted (Black)
- [x] Linting clean (Ruff)
- [x] Documentation updated
- [x] CHANGELOG.md updated
EOF
)"
```

**Via GitHub Web UI:**
1. Go to repository → Pull Requests → New PR
2. Select base: `main`, compare: `your-branch`
3. Fill in template
4. Create PR

### 6. PR Review Process

**Automated Checks (must pass):**
- ✅ Backend tests (pytest)
- ✅ Frontend tests (if UI changes)
- ✅ Code formatting (Black, Ruff)
- ✅ Type checking (mypy)
- ✅ Security scan (no secrets, dependency audit)
- ✅ Risk-critical code validation (Decimal usage, kill switch)
- ✅ Coverage threshold (≥50%)

**Manual Review:**
- Code quality and readability
- Test coverage adequacy
- Documentation completeness
- Architecture consistency

### 7. Merge to Main

**After all checks pass and approval:**

```bash
# Option 1: GitHub UI (recommended)
# Click "Squash and merge" button

# Option 2: CLI
gh pr merge <pr-number> --squash --delete-branch

# Example:
gh pr merge 42 --squash --delete-branch
```

**Squash Merge Benefits:**
- Clean linear history
- One commit per feature
- Easy to revert if needed

### 8. Cleanup

```bash
# Switch to main
git checkout main

# Pull latest (includes your merged PR)
git pull origin main

# Delete local feature branch (if not auto-deleted)
git branch -d feature/my-new-feature
```

## 🚨 Common Scenarios

### Scenario 1: Update Branch with Latest Main

```bash
# While on feature branch
git checkout main
git pull origin main
git checkout feature/my-feature
git rebase main

# If conflicts, resolve them
git add <resolved-files>
git rebase --continue

# Force push (rebase rewrites history)
git push --force-with-lease
```

### Scenario 2: Fix Failing CI Checks

```bash
# Make fixes locally
# Run tests
pytest

# Commit fix
git commit -m "fix: Resolve CI test failures"

# Push
git push

# CI re-runs automatically
```

### Scenario 3: Amend Last Commit

```bash
# Make additional changes
git add <files>

# Amend previous commit
git commit --amend --no-edit

# Force push (rewrites history)
git push --force-with-lease
```

**⚠️ Warning**: Only amend commits that haven't been merged. Never amend commits on main.

### Scenario 4: Revert Merged PR

```bash
# Create revert PR
gh pr create --title "revert: Undo PR #42" \
  --body "Reverts #42 due to <reason>"

# Or via git
git revert -m 1 <merge-commit-hash>
git push
```

### Scenario 5: Cherry-Pick Commit

```bash
# Get commit hash
git log --oneline

# Cherry-pick to current branch
git cherry-pick <commit-hash>

# Push
git push
```

## 📊 Workflow for Different Change Types

### Small Bug Fix (< 50 lines)
```bash
1. Create fix/bug-name branch
2. Make fix + add test
3. Commit with "fix:" prefix
4. Push and create PR
5. Merge when CI passes (usually < 15 min)
```

### New Feature (50-500 lines)
```bash
1. Create feature/feature-name branch
2. Implement incrementally with tests
3. Commit regularly ("feat:", "test:", "docs:")
4. Push and create PR when complete
5. Address review feedback
6. Merge when approved
```

### Large Refactoring (500+ lines)
```bash
1. Create refactor/refactor-name branch
2. Plan migration (document in docs/archive/)
3. Execute in small, testable increments
4. Keep tests passing at each step (crucial!)
5. Document daily progress
6. Create PR with comprehensive description
7. Expect longer review (coordinate with team)
8. Merge when all checks pass + approval
```

## 🔒 Protected Branches

### Main Branch Protection Rules

**Enforced by GitHub:**
- ✅ Require pull request reviews (1 approval)
- ✅ Require status checks to pass
- ✅ Require conversation resolution
- ✅ Restrict who can push (admins only)

**Status Checks Required:**
- Backend - Lint & Test
- Frontend - Lint & Test (Phase 4+)
- Security - Dependency Audit
- Risk Manager - Extra Validation
- ✅ Quality Gate - PASSED

### Override Protection (Emergency Only)

```bash
# Requires admin permissions
gh pr merge <pr-number> --admin --squash
```

**When to use:**
- Critical production bug fix
- Security vulnerability patch
- Never for regular development

## 📝 Commit Best Practices

### DO ✅
- Write descriptive commit messages
- Keep commits focused (one logical change)
- Include "why" not just "what"
- Reference issue numbers
- Update tests with code changes
- Run tests before committing

### DON'T ❌
- Commit broken code
- Mix unrelated changes
- Write vague messages ("fix bug", "update code")
- Commit commented-out code
- Include secrets or API keys
- Skip pre-commit hooks

## 🎓 Advanced Workflows

### Interactive Rebase (Clean Up History)

```bash
# Rebase last 5 commits interactively
git rebase -i HEAD~5

# Options in editor:
# pick   - keep commit as-is
# reword - change commit message
# squash - merge with previous commit
# drop   - delete commit
```

**Use case:** Clean up "WIP" commits before creating PR

### Stash Changes

```bash
# Save work-in-progress
git stash save "WIP: implementing feature X"

# List stashes
git stash list

# Apply stash
git stash apply stash@{0}

# Apply and remove
git stash pop
```

**Use case:** Quickly switch branches without committing

### Bisect (Find Bug-Introducing Commit)

```bash
# Start bisect
git bisect start
git bisect bad              # Current commit is bad
git bisect good <commit>    # Known good commit

# Git checks out middle commit
# Test it, then:
git bisect good  # or
git bisect bad

# Repeat until bug found
git bisect reset  # Exit bisect mode
```

**Use case:** Identify when a bug was introduced

## 🔍 Git Aliases (Optional Productivity Boost)

Add to `~/.gitconfig`:

```ini
[alias]
    st = status -sb
    co = checkout
    br = branch
    ci = commit
    ca = commit --amend --no-edit
    lg = log --oneline --graph --decorate --all
    last = log -1 HEAD --stat
    unstage = reset HEAD --
    undo = reset --soft HEAD~1
```

Usage:
```bash
git st      # Instead of git status -sb
git lg      # Pretty log graph
git last    # Show last commit details
```

## 📚 Resources

### Internal Documentation
- [CHANGELOG.md](../../CHANGELOG.md) - Version history
- [DOCUMENTATION_GUIDE.md](../DOCUMENTATION_GUIDE.md) - Where to document
- [development-workflow.md](./development-workflow.md) - Local dev setup

### External Resources
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Git Best Practices](https://git-scm.com/book/en/v2)

---

**Maintained by**: Development team
**Last Updated**: 2025-10-29
**Version**: 1.0
