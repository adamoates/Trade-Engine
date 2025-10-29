# Documentation Guide

This guide explains where to find and how to update documentation in this project.

## 📁 Documentation Structure (Single Source of Truth)

### Root Directory Files

| File | Purpose | When to Update |
|------|---------|----------------|
| `README.md` | Project overview, quick start, high-level architecture | When adding major features or changing project structure |
| `ROADMAP.md` | Development timeline, phases, milestones, gates | At the end of each phase or when adjusting timeline |
| `CHANGELOG.md` | Version history, release notes, breaking changes | With every commit to main (or before releases) |
| `.claude/CLAUDE.md` | **AI Assistant Instructions** - project context, coding standards, critical rules | When changing architecture, adding new patterns, or updating development rules |

### Documentation Directories

#### `docs/` - Technical Documentation
- `docs/README.md` - Documentation index and guide
- `docs/deployment.md` - Production deployment procedures
- `docs/TEST_REPORT_*.md` - Test coverage reports (dated)
- `docs/PHASE*-AUDIT-REPORT.md` - Phase completion audits

#### `docs/architecture/` - System Design
- Architecture decisions and patterns
- System design documents
- Trade fingerprinting and auditing systems

#### `docs/guides/` - How-To Guides
- **Development**: `development-workflow.md` - Local development setup
- **CI/CD**: `ci-cd-setup.md`, `github-actions-guide.md`
- **Data**: `data-pipeline-guide.md`, `data-validation-guide.md`
- **Docker**: `docker-performance.md`
- **Testing**: `using-test-fixtures.md`
- **Live Server**: `live-server-update.md`, `live-server-quick-reference.md`
- **Tools**: `python-tool-structure.md`, `pipeline-one-liners.md`

#### `docs/reports/` - Historical Reports
- Sprint summaries
- Verification reports
- Performance analysis

#### `docs/archive/` - Historical Documentation
- Refactoring documentation (day-by-day summaries)
- Deprecated guides
- Legacy architecture docs

### Test Documentation
- `tests/fixtures/README.md` - Test data and fixture usage

## 🎯 When to Use Each File

### For New Contributors
1. **Start here**: `README.md` - Project overview
2. **Then**: `.claude/CLAUDE.md` - Coding standards and critical rules
3. **Then**: `docs/guides/development-workflow.md` - How to set up and contribute

### For Adding Features
1. **Update**: `CHANGELOG.md` - Document your changes
2. **Update**: `.claude/CLAUDE.md` - If adding new patterns or rules
3. **Update**: `ROADMAP.md` - If feature affects timeline
4. **Create**: New guide in `docs/guides/` if complex feature

### For Architecture Changes
1. **Update**: `.claude/CLAUDE.md` - AI assistant needs to know
2. **Create**: Document in `docs/architecture/`
3. **Update**: `README.md` - Update architecture section
4. **Update**: `CHANGELOG.md` - Document breaking changes

### For Releases
1. **Update**: `CHANGELOG.md` - Move [Unreleased] to version
2. **Create**: Test report in `docs/`
3. **Create**: Phase audit report if completing phase

## 📝 Documentation Standards

### Markdown Style
- Use GitHub-flavored markdown
- File names: `kebab-case.md` (enforced by pre-commit hook)
- Location: Root files (README, ROADMAP, CHANGELOG) or `docs/` subdirectories

### Code Examples
Always include:
- Language identifier for syntax highlighting
- Comments explaining non-obvious code
- Link to actual source file when referencing implementation

### Links
- Use relative links: `[Guide](docs/guides/setup.md)` ✅
- Not absolute: `[Guide](https://github.com/.../setup.md)` ❌

## 🚫 What NOT to Document

### Do NOT create documentation for:
- Individual functions (use docstrings instead)
- Implementation details that change frequently (use code comments)
- Temporary scripts or tools (comment them inline)
- Personal notes (keep in local files outside repo)

### Do NOT duplicate documentation:
- If it exists in `.claude/CLAUDE.md`, link to it
- If it exists in code docstrings, link to source
- If it exists in a guide, reference the guide

## 🔄 Documentation Workflow

### Before Committing
1. Check if documentation update is needed
2. Follow naming conventions (kebab-case)
3. Place in correct directory (see structure above)
4. Update `CHANGELOG.md` if user-facing change

### During PR Review
- Reviewers check documentation completeness
- CI enforces file naming and location (see `.claude/hooks/pre-commit.sh`)

### After Merging
- Archive old guides to `docs/archive/` if superseded
- Update documentation index if structure changed

## 🎓 Best Practices

### Write for Your Future Self
Documentation should answer: "What would I need to know if I came back to this project in 6 months?"

### Keep It DRY (Don't Repeat Yourself)
- Single source of truth for each topic
- Link to other docs rather than copying
- Update in one place

### Make It Scannable
- Use tables for comparisons
- Use bullet points for lists
- Use headers for sections
- Include code examples

### Version Everything
- Date reports: `TEST_REPORT_2025-10-23.md`
- Version guides if they change significantly
- Archive old versions in `docs/archive/`

## 📚 Documentation Types

| Type | Location | Example | Frequency |
|------|----------|---------|-----------|
| **Project Overview** | `README.md` | Project description, quick start | Rarely (major changes only) |
| **Development Plan** | `ROADMAP.md` | Phases, milestones, gates | Phase boundaries |
| **Version History** | `CHANGELOG.md` | Release notes, changes | Every commit to main |
| **AI Instructions** | `.claude/CLAUDE.md` | Coding standards, critical rules | Architecture changes |
| **How-To Guides** | `docs/guides/` | Step-by-step procedures | When adding complex features |
| **Architecture** | `docs/architecture/` | System design, decisions | Major refactorings |
| **Reports** | `docs/reports/` | Sprint summaries, audits | Sprint/phase completion |
| **Historical** | `docs/archive/` | Old docs, deprecated guides | When superseding old docs |

## 🔍 Finding Documentation

### "Where do I find...?"

**...project overview?** → `README.md`
**...development timeline?** → `ROADMAP.md`
**...coding standards?** → `.claude/CLAUDE.md`
**...version history?** → `CHANGELOG.md`
**...setup instructions?** → `docs/guides/development-workflow.md`
**...deployment guide?** → `docs/deployment.md`
**...CI/CD setup?** → `docs/guides/ci-cd-setup.md`
**...architecture decisions?** → `docs/architecture/`
**...refactoring history?** → `docs/archive/refactoring-*.md`
**...test coverage?** → `docs/TEST_REPORT_*.md`

---

**Maintained by**: Project contributors
**Last Updated**: 2025-10-29
**Version**: 1.0
