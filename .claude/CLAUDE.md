# AlphaTales Refactor Agent

This is an AI-assisted, rules-driven code refactoring system powered by Claude Agent SDK.

## Project Overview

The system accepts a project folder path, loads refactor rules, then performs a full automated workflow:
1. Project scanning
2. Rule interpretation
3. Multi-pass refactoring
4. Multi-pass rule-compliance validation
5. Build & test execution
6. Reporting

## Philosophy

- **Never guess**: Always refactor according to explicit written rules (Skills)
- **Verify changes**: Use structured subagents and builds to validate
- **Minimize tokens**: Be efficient with context to reduce API costs
- **Preserve behavior**: Refactoring should not change functionality unless explicitly allowed

## Architecture

### Subagents (in `.claude/agents/`)
- `project-scanner` - Scans project, builds file manifest
- `rules-interpreter` - Converts rules to structured plan
- `nextjs-refactorer` - Refactors frontend code
- `python-refactorer` - Refactors backend code
- `compliance-checker` - Validates rule compliance
- `build-runner` - Runs build/test commands
- `summary-reporter` - Generates final report

### Skills (in `.claude/skills/`)
- `refactor_rules` - Central rulebook for all refactoring
- `architecture_guidelines` - Project structure and layering rules
- `migration_patterns` - Framework migration patterns (future)

## Output Directory

All refactoring artifacts are stored in `.refactor/`:
- `manifest.json` - Project file manifest
- `refactor_plan.json` - Structured refactoring plan
- `logs/` - Per-pass change logs
- `compliance_report.json` - Compliance check results
- `build_report.json` - Build/test results
- `summary.md` - Human-readable summary

## Token Efficiency Guidelines

1. Use Glob patterns for file discovery, not recursive reads
2. Read only necessary file sections, not entire files
3. Use Edit for targeted changes, not full file rewrites
4. Summarize outputs, don't include full logs
5. Cache intermediate results in `.refactor/`

## Supported Languages

- Python (backend)
- TypeScript/JavaScript (Next.js frontend)
- Future: Xamarin to React Native migration
