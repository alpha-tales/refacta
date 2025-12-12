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

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Create a Virtual Environment](#step-2-create-a-virtual-environment)
  - [Step 3: Activate the Virtual Environment](#step-3-activate-the-virtual-environment)
  - [Step 4: Install Dependencies](#step-4-install-dependencies)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Interactive Mode (Recommended)](#interactive-mode-recommended)
  - [Automated Pipeline](#automated-pipeline)
  - [CLI Commands](#cli-commands)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Refactoring Pipeline](#refactoring-pipeline)
- [Output Directory](#output-directory)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10 or higher** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **Anthropic API Key** - [Get your API key](https://console.anthropic.com/)

To verify your Python version:

```bash
python --version
# or
python3 --version
```

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/alphatales/refacta.git
cd refacta
```

### Step 2: Create a Virtual Environment

Creating a virtual environment isolates the project dependencies from your system Python installation.

**On macOS/Linux:**

```bash
python3 -m venv venv
```

**On Windows:**

```bash
python -m venv venv
```

This creates a `venv` directory containing an isolated Python environment.

### Step 3: Activate the Virtual Environment

You must activate the virtual environment before installing dependencies or running the project.

**On macOS/Linux:**

```bash
source venv/bin/activate
```

**On Windows (Command Prompt):**

```bash
venv\Scripts\activate.bat
```

**On Windows (PowerShell):**

```bash
venv\Scripts\Activate.ps1
```

> **Note**: When activated, you'll see `(venv)` prefix in your terminal prompt.

To deactivate the virtual environment when you're done:

```bash
deactivate
```

### Step 4: Install Dependencies

With the virtual environment activated, install the project dependencies:

**Option A: Install from requirements.txt (recommended for development)**

```bash
pip install -r requirements.txt
```

**Option B: Install as an editable package**

```bash
pip install -e .
```

This installs the package in development mode, allowing you to make changes to the code without reinstalling.

**Option C: Install with development dependencies**

```bash
pip install -e ".[dev]"
```

This includes additional tools for testing and linting (pytest, ruff, mypy, black).

---

## Configuration

### Set Up Your API Key

The refactor agent requires an Anthropic API key to communicate with Claude.

**Option 1: Create a `.env` file (recommended)**

```bash
# Create the .env file
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

Replace `your-api-key-here` with your actual API key from [Anthropic Console](https://console.anthropic.com/).

**Option 2: Export as environment variable**

**On macOS/Linux:**

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

**On Windows (Command Prompt):**

```bash
set ANTHROPIC_API_KEY=your-api-key-here
```

**On Windows (PowerShell):**

```bash
$env:ANTHROPIC_API_KEY="your-api-key-here"
```

> **Security Note**: Never commit your `.env` file to version control. The `.gitignore` file should already exclude it.

---

## Usage

### Interactive Mode (Recommended)

Launch the interactive console for a guided refactoring experience:

```bash
# Start the Textual TUI (default)
python run.py

# Start with a specific project path
python run.py -p /path/to/your/project

# Use classic Rich-based console UI
python run.py --classic

# Specify a different Claude model
python run.py -m claude-sonnet-4-20250514
```

The interactive mode provides:
- Split panel layout with chat, file tree, and progress indicators
- Visual diff viewer with red/green highlighting
- Menu-based operation selection (refactor / migrate)
- `@` triggered file autocomplete
- Real-time progress tracking

### Automated Pipeline

Run the complete refactoring pipeline non-interactively:

```bash
# Full refactoring pipeline
python run.py run ./my-project ./rules/python-rules.md

# Dry run (preview changes without modifying files)
python run.py run ./my-project ./rules/general-rules.md --dry-run

# Quiet mode (suppress banner and verbose output)
python run.py run ./my-project ./rules.md --quiet
```

### CLI Commands

If you installed the package (`pip install -e .`), you can use the CLI directly:

```bash
# Show help
refactor-agent --help

# Show version
refactor-agent --version

# Scan a project (without refactoring)
refactor-agent scan ./my-project

# List available rule files
refactor-agent list-rules ./rules

# Run full pipeline
refactor-agent run ./project ./rules.md
```

### Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Path to the project directory |
| `--model` | `-m` | Claude model to use (default: claude-haiku-4-5-20251001) |
| `--classic` | `-c` | Use classic Rich console instead of Textual TUI |
| `--dry-run` | `-n` | Preview changes without modifying files |
| `--quiet` | `-q` | Suppress banner and verbose output |
| `--version` | `-v` | Show version and exit |
| `--help` | | Show help message |

---

## Architecture

The system uses a multi-agent architecture where each agent specializes in a specific task:

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

---

## Project Structure

```
refacta/
├── .claude/
│   ├── agents/              # Subagent definitions (7 agents)
│   │   ├── project-scanner.md
│   │   ├── rules-interpreter.md
│   │   ├── python-refactorer.md
│   │   ├── nextjs-refactorer.md
│   │   ├── compliance-checker.md
│   │   ├── build-runner.md
│   │   └── summary-reporter.md
│   ├── skills/              # Reusable knowledge bases
│   │   ├── refactor_rules/
│   │   ├── architecture_guidelines/
│   │   └── migration_patterns/
│   ├── settings.json        # Agent configuration
│   └── CLAUDE.md            # Project instructions
├── src/refactor_agent/
│   ├── __init__.py
│   ├── cli.py               # CLI entry point (Typer)
│   ├── orchestrator.py      # Pipeline coordinator
│   ├── sdk/                 # Claude Agent SDK wrapper
│   │   └── client.py
│   ├── pipeline/            # 5-stage refactoring pipeline
│   │   ├── scan.py
│   │   ├── apply_rules.py
│   │   ├── verify_rules.py
│   │   ├── build_run.py
│   │   └── reporting.py
│   ├── rules/               # Rules model and loader
│   │   ├── model.py
│   │   └── loader.py
│   ├── console/             # Interactive UI components
│   │   ├── app.py
│   │   ├── ui.py
│   │   ├── textual_ui.py
│   │   ├── menu.py
│   │   ├── session.py
│   │   ├── autocomplete.py
│   │   └── diff_viewer.py
│   └── utils/               # File ops, logging
│       ├── file_ops.py
│       └── logger.py
├── tests/                   # Test suite
├── run.py                   # Main entry point
├── pyproject.toml           # Project configuration
├── requirements.txt         # Dependencies
└── README.md
```

---

## Refactoring Pipeline

The automated pipeline consists of 6 stages:

1. **Scan**: Discover files, build project manifest
2. **Interpret**: Convert rules to structured execution plan
3. **Apply**: Multi-pass refactoring (3 passes)
   - Pass 1: Structural cleanup (dead code, imports)
   - Pass 2: Local refactors (helpers, naming, types)
   - Pass 3: Cross-file consistency
4. **Verify**: 3-round compliance checking
5. **Build**: Run lint, build, and tests
6. **Report**: Generate summary and artifacts

---

## Output Directory

All refactoring artifacts are stored in `.refactor/` within the target project:

| File | Description |
|------|-------------|
| `manifest.json` | Project file manifest |
| `refactor_plan.json` | Structured execution plan |
| `logs/` | Per-pass change logs |
| `compliance_report.json` | Validation results |
| `build_report.json` | Build/test results |
| `summary.md` | Human-readable report |
| `backups/` | File backups (safety net) |

---

## Troubleshooting

### Common Issues

**"ANTHROPIC_API_KEY not found"**

Ensure your API key is set:
```bash
# Check if the key is set
echo $ANTHROPIC_API_KEY

# Set it if missing
export ANTHROPIC_API_KEY="your-key-here"
```

**"Module not found" errors**

Make sure your virtual environment is activated and dependencies are installed:
```bash
source venv/bin/activate  # or appropriate command for your OS
pip install -r requirements.txt
```

**"Python version too old"**

This project requires Python 3.10+. Check your version:
```bash
python --version
```

**Permission denied on Windows PowerShell**

If you can't activate the virtual environment:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**TUI not rendering correctly**

Try using the classic Rich UI instead:
```bash
python run.py --classic
```

---

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=refactor_agent
```

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

---

## Philosophy

- **Never guess**: Always refactor according to explicit written rules
- **Verify changes**: Use structured subagents and builds to validate
- **Minimize tokens**: Be efficient with context to reduce API costs
- **Preserve behavior**: Refactoring should not change functionality

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions welcome! Please read the project guidelines in `.claude/CLAUDE.md`.

---

Built with Claude AI and the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk)
