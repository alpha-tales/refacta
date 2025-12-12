# AlphaTales Refactor Agent

An AI-powered, rules-driven code refactoring system built on the Claude Agent SDK. Uses a multi-agent architecture to automatically analyze, plan, and refactor codebases while preserving behavior.

## Features

- **Rules-Driven Refactoring**: Explicit, auditable refactoring rules in Markdown
- **Multi-Agent Architecture**: Specialized agents for scanning, refactoring, validation
- **Multi-Language Support**: Python and TypeScript/JavaScript (Next.js)
- **Interactive Console**: Textual TUI or classic Rich UI with autocomplete
- **Safety First**: Automatic backups, compliance checking, build validation
- **Cost Optimized**: Token-efficient prompts with session management
- **Detailed Reports**: Human-readable summaries and structured JSON outputs

## Architecture

```
Orchestrator
├── project-scanner      → Discovers files, builds manifest
├── rules-interpreter    → Converts rules to structured plan
├── python-refactorer    → Refactors backend code
├── nextjs-refactorer    → Refactors frontend code
├── compliance-checker   → Validates rule compliance
├── build-runner         → Runs build/tests
└── summary-reporter     → Generates reports
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/alphatales/refacta.git
cd refacta

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

### Configuration

```bash
# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

Get your API key from: https://console.anthropic.com/

### Usage

**Interactive Mode (default):**
```bash
# Launch interactive console
python run.py

# With specific project path
python run.py -p ./my-project

# Classic Rich UI instead of Textual TUI
python run.py --classic
```

**Automated Pipeline:**
```bash
# Full refactoring pipeline
refactor-agent run ./project ./rules.md

# Dry run (no changes)
refactor-agent run ./project ./rules.md --dry-run

# Scan only
refactor-agent scan ./project

# List available rules
refactor-agent list-rules ./rules
```

## Project Structure

```
refacta/
├── .claude/
│   ├── agents/              # Subagent definitions (7 agents)
│   ├── skills/              # Reusable knowledge bases
│   ├── settings.json        # Agent configuration
│   └── CLAUDE.md            # Project instructions
├── src/refactor_agent/
│   ├── cli.py               # CLI entry point (Typer)
│   ├── orchestrator.py      # Pipeline coordinator
│   ├── sdk/                 # Claude Agent SDK wrapper
│   ├── pipeline/            # 5-stage refactoring pipeline
│   ├── rules/               # Rules model and loader
│   ├── console/             # Interactive UI components
│   └── utils/               # File ops, logging
├── tests/                   # Test suite
├── pyproject.toml           # Project configuration
└── requirements.txt         # Dependencies
```

## Refactoring Pipeline

1. **Scan**: Discover files, build manifest
2. **Interpret**: Convert rules to structured plan
3. **Apply**: Multi-pass refactoring (3 passes)
   - Pass 1: Structural cleanup (dead code, imports)
   - Pass 2: Local refactors (helpers, naming, types)
   - Pass 3: Cross-file consistency
4. **Verify**: 3-round compliance checking
5. **Build**: Run lint, build, and tests
6. **Report**: Generate summary and artifacts

## Output Directory

All artifacts are stored in `.refactor/`:
- `manifest.json` - Project file manifest
- `refactor_plan.json` - Structured execution plan
- `logs/` - Per-pass change logs
- `compliance_report.json` - Validation results
- `build_report.json` - Build/test results
- `summary.md` - Human-readable report
- `backups/` - File backups

## Requirements

- Python 3.10+
- Anthropic API key
- Claude Agent SDK 0.1.14+

## Philosophy

- **Never guess**: Always refactor according to explicit written rules
- **Verify changes**: Use structured subagents and builds to validate
- **Minimize tokens**: Be efficient with context to reduce API costs
- **Preserve behavior**: Refactoring should not change functionality

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read the project guidelines in `.claude/CLAUDE.md`.

---

Built with Claude AI and the Claude Agent SDK
