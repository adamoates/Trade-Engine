# MFT Trading Bot - Comprehensive Guides

This directory contains detailed operational guides and reference documentation for developing, deploying, and maintaining the MFT trading bot.

## What's in This Directory

These are **comprehensive reference guides** that provide deep-dive explanations, step-by-step procedures, and complete context for major aspects of the project. Unlike the brief documentation in the main docs/ folder, these guides are designed to be read top-to-bottom or used as reference material.

## Available Guides

### 🚀 **ci-cd-setup.md**
Quick-start guide for GitHub Actions CI/CD pipeline setup.

**When to use**: Setting up the project for the first time, troubleshooting CI/CD issues

**Contents**:
- Step-by-step GitHub Actions setup
- Required secrets configuration
- Branch protection setup
- Phase-by-phase activation plan
- Common issues and solutions

### 📦 **github-actions-guide.md**
Complete reference for GitHub Actions workflows, best practices, and troubleshooting.

**When to use**: Understanding how CI/CD works, debugging workflow failures, advanced configuration

**Contents**:
- Complete workflow architecture explanation
- Detailed setup instructions
- Phase-by-phase activation guide
- Development best practices
- Comprehensive troubleshooting
- Advanced configuration options

### 🔧 **development-workflow.md** *(Coming in Phase 2)*
Daily development workflow patterns and team collaboration practices.

**Contents** (planned):
- Feature development workflow
- Code review procedures
- Testing strategies
- Git workflow (branching, merging, rebasing)
- Team collaboration patterns

### 📋 **project-setup-checklist.md** *(Coming in Phase 0)*
Complete checklist for setting up development environment from scratch.

**Contents** (planned):
- Environment setup steps
- Required tools installation
- GitHub repository configuration
- VPS setup procedures
- Exchange API configuration

### 🎯 **risk-management-procedures.md** *(Coming in Phase 2)*
Operational procedures for risk management, kill switches, and emergency protocols.

**Contents** (planned):
- Kill switch activation procedures
- Risk limit monitoring
- Emergency shutdown protocols
- Incident response procedures
- Post-incident analysis

### 🏗️ **architecture-decisions.md** *(Coming in Phase 2)*
Architectural decision records (ADRs) documenting major technical choices.

**Contents** (planned):
- Technology stack decisions
- Architecture pattern choices
- Trade-offs analysis
- Lessons learned
- Decision rationale documentation

## How to Use These Guides

### For New Team Members
1. Start with `project-setup-checklist.md`
2. Read `ci-cd-setup.md` to understand deployment
3. Study `development-workflow.md` for daily patterns
4. Reference other guides as needed

### For Troubleshooting
1. Check `github-actions-guide.md` for CI/CD issues
2. Check `risk-management-procedures.md` for trading bot issues
3. Reference architecture decisions for design questions

### For Reference
- Keep these open in your browser/editor while working
- Use table of contents to jump to relevant sections
- Bookmark frequently referenced sections

## Contributing to Guides

When adding new guides, follow this structure:

### Guide Template
```markdown
# [Guide Title]

## Overview
Brief description of what this guide covers

## Table of Contents
1. Section 1
2. Section 2
...

## Sections
Clear, detailed sections with:
- Step-by-step instructions
- Code examples
- Troubleshooting tips
- Cross-references to other docs

## Quick Reference
Commands, checklists, or summaries at the end
```

### Naming Convention
- Use descriptive kebab-case names
- End with `-guide.md`, `-procedures.md`, or `-checklist.md`
- Be specific about content (not generic like "best-practices")

### When to Create a New Guide
Create a new guide when:
- Topic requires >500 lines of detailed explanation
- Multiple team members ask about the same process
- Topic spans multiple phases or components
- Content is primarily procedural/operational

**Don't create a guide for**:
- Brief API documentation (put in code comments)
- Component-level docs (put near the code)
- Quick reference (put in main docs/README.md)

## Maintenance

### Review Schedule
- **Monthly**: Update with new learnings from development
- **Phase Completion**: Add phase-specific guides
- **After Incidents**: Document new procedures/lessons

### Keep Updated
- Update guides when procedures change
- Add troubleshooting sections based on real issues
- Remove outdated information promptly
- Add cross-references to related guides

## Related Documentation

### Main Documentation (`docs/`)
- **README.md**: Quick reference and documentation index
- **deployment.md**: Production deployment overview
- **architecture.md** *(future)*: System architecture overview

### Project Documentation (`/Users/adamoates/Documents/trader/`)
- **mft-architecture.md**: Complete technical architecture specification
- **mft-strategy-spec.md**: Trading strategy details
- **mft-risk-management.md**: Risk framework
- **mft-roadmap.md**: Development phases
- **mft-dev-log.md**: Development journal template

### Code Documentation
- **CLAUDE.md**: AI assistant context (project overview, standards, patterns)
- **ROADMAP.md**: Development roadmap with phase gates
- **README.md**: Project introduction

---

**Remember**: These guides are living documents. Update them as you learn, add real troubleshooting examples, and keep them practical and actionable.
