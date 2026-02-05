# CMAI - AI-Powered Commit Message Normalizer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

CMAI is a CLI tool that uses AI to transform informal commit descriptions into standardized, professional Git commit messages based on your staged changes.

## 🚀 Quick Start

### 1. Installation

Install via `uv` (recommended) or `pip`:

```bash
# Install with all providers support
uv tool install cmai[all-providers]
# OR
pip install cmai[all-providers]

# For specific providers only: cmai[openai], cmai[ollama], cmai[anthropic], etc.
```

### 2. Configuration

Create the configuration file at `~/.config/cmai/settings.env`:

```env
# --- Remote Provider Example (OpenAI, DeepSeek, Zai, etc.) ---
PROVIDER=openai
API_KEY=your_api_key_here
MODEL=gpt-4o-mini
# API_BASE=... (Optional: Only needed for non-standard endpoints)

# --- Anthropic (Claude) Provider Example ---
# PROVIDER=anthropic
# API_KEY=your_anthropic_api_key_here
# MODEL=claude-3-5-sonnet-20241022
# ENABLE_THINKING=true
# THINKING_BUDGET=1024

# --- Local Provider Example (Ollama) ---
# PROVIDER=ollama
# OLLAMA_HOST=http://localhost:11434
# MODEL=qwen2.5:7b
```

**Supported Providers:** openai, bailian, deepseek, siliconflow, anthropic, claude, zai (智谱), ollama.

**Tip:** You can also set CMAI_API_KEY or ANTHROPIC_API_KEY as environment variables instead of putting them in the config file.

### 3. Usage

Stage your changes and run cmai:

```bash
git add .
cmai "fix a bug"
```

The tool will output a normalized message and prompt for action:

- [c]ommit: Execute git commit.
- [e]dit: Edit the message manually.
- [a]bort: Cancel.

If a commit error occurs, an appropriate error message will be displayed and retained here. You can open a new terminal to fix these issues and then input 'c' to proceed with the commit.

## 🛠 CLI Options

```bash
cmai [MESSAGE] [OPTIONS]

Options:
  -c, --config TEXT    Path to a custom configuration file
  -r, --repo TEXT      Path to the git repository (default: current dir)
  -l, --language TEXT  Target language for the commit message (e.g., "Chinese")
```

## 📦 Development

```bash
git clone [https://github.com/yumuzhihan/cmai.git](https://github.com/yumuzhihan/cmai.git)
cd cmai
uv sync --all-extras    # Or other groups
python -m pytest        # Run tests
```

## 📄 License

This project is licensed under the [MIT License](https://github.com/yumuzhihan/cmai/blob/main/LICENSE).
