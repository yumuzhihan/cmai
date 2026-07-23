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

Run the interactive configuration wizard:

```bash
cmai config
```

It manages the global file at `~/.config/cmai/settings.env`. On the first run,
the directory and file are created only after you review the redacted summary
and confirm the save. Later runs let you reconfigure everything or change only
the Provider, commit rules, or optional settings. API keys are hidden in the
UI, and the saved file is owner-readable/writable only on POSIX systems.

Install the provider extra you intend to use before opening the wizard:

```bash
uv tool install 'cmai[openai]'       # OpenAI-compatible providers
uv tool install 'cmai[ollama]'       # Local Ollama
uv tool install 'cmai[anthropic]'    # Claude
uv tool install 'cmai[zai]'          # Zhipu AI
# Or use pip
# pip install 'cmai[openai]'
# pip install 'cmai[ollama]'
# pip install 'cmai[anthropic]'
# pip install 'cmai[zai]'
```

The wizard discovers the providers that are actually installed. It supports
custom/proxy endpoints through `API_BASE`; for Ollama, that endpoint is also
used as the host when a legacy `OLLAMA_HOST` is not configured.

For automation or a temporary configuration, `--config` still accepts a custom
dotenv file and does not change the global configuration:

```bash
cmai commit "fix a bug" --config /path/to/settings.env
```

You can still write a custom file manually when needed:

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

# --- Commit Specification Rules ---
COMMIT_SPEC=conventional
COMMIT_STRICT=true
# COMMIT_ALLOWED_TYPES=feat,fix,docs,chore
COMMIT_SCOPE_POLICY=optional
COMMIT_SUBJECT_MAX_LEN=72
COMMIT_HEADER_MAX_LEN=100
COMMIT_SUBJECT_CASE=lower
COMMIT_ALLOW_BANG=true

# --- Large Diff and Context Optimization ---
MAX_DIFF_LENGTH=8000
MAX_DIFF_FILE_LINES=50
MAX_DIFF_FILES_FOR_AI=30
ENABLE_SPLIT_SUGGESTION=true
SPLIT_CONFIDENCE_THRESHOLD=0.75
DIFF_SUMMARY_CONCURRENCY=5
RETRY_MAX_ATTEMPTS=5
RETRY_BASE_DELAY_SECONDS=2.0
RETRY_MAX_DELAY_SECONDS=30.0
```

**Supported Providers:** openai, bailian, deepseek, siliconflow, anthropic, claude, zai (智谱), ollama.

**Tip:** You can also set `CMAI_API_KEY` or `ANTHROPIC_API_KEY` as environment variables instead of putting secrets in the config file. Never commit `settings.env` or share its contents.

### Prompt Template Variables

`PROMPT_TEMPLATE` must contain all three variables below. The interactive
wizard can restore the built-in template or open your editor, and stores
multi-line templates safely as a single encoded dotenv value.

- `{user_input}` — your informal commit description
- `{diff_content}` — staged-change context
- `{language}` — requested response language

Older templates using `{{user_input}}`, `{{diff_content}}`, and `{{language}}`
continue to work; the wizard offers to migrate them when you edit one.

### 3. Usage

Stage your changes and run cmai:

```bash
git add .
cmai "fix a bug"
```

The tool will output a normalized message and prompt for action:

- [c]ommit: Execute git commit.
- [e]dit: Edit the message manually.
- [r]egenerate: Ask the model to regenerate. You can provide an optional additional prompt.
- [a]bort: Cancel.

When `COMMIT_STRICT=true`, non-compliant messages cannot be committed.
The CLI will show warnings and only allow `edit`, `regenerate`, or `abort` until the message passes validation.

For very large staged diffs, CMAI now falls back to per-file truncated diff previews instead of only file names.
When a staged diff exceeds `MAX_DIFF_LENGTH`, CMAI asks whether to generate file-level summaries or use only the staged file list for commit generation.
During file summarization, CMAI runs file summaries concurrently and shows a single `tqdm` progress bar instead of printing each file's summary.

When providers hit rate limits (for example `403 RPM limit exceeded` or `429`), CMAI automatically retries with exponential backoff.
If final commit generation still fails after retries, CMAI falls back to a local heuristic commit message instead of exiting immediately.

If a commit error occurs, an appropriate error message will be displayed and retained here. You can open a new terminal to fix these issues and then input 'c' to proceed with the commit.

## 🛠 CLI Options

```bash
cmai [MESSAGE] [OPTIONS]
cmai commit [MESSAGE] [OPTIONS]
cmai config

Options:
  -c, --config TEXT    Path to a custom configuration file
  -r, --repo TEXT      Path to the git repository (default: current dir)
  -l, --language TEXT  Target language for the commit message (e.g., "Chinese")
```

## ✅ Commit Specs and Formatting Preferences

- `COMMIT_SPEC`: `conventional` or `angular`
- `COMMIT_STRICT`: if `true`, block commit until message is valid
- `COMMIT_ALLOWED_TYPES`: optional comma-separated override for allowed types
- `COMMIT_SCOPE_POLICY`: `optional`, `required`, or `forbid`
- `COMMIT_SUBJECT_MAX_LEN`: max subject length
- `COMMIT_HEADER_MAX_LEN`: max full header length
- `COMMIT_SUBJECT_CASE`: `lower`, `sentence`, or `any`
- `COMMIT_ALLOW_BANG`: whether `!` is allowed in header
- `MAX_DIFF_LENGTH`: max characters for raw staged diff context
- `MAX_DIFF_FILE_LINES`: per-file changed lines kept in truncated preview mode
- `MAX_DIFF_FILES_FOR_AI`: max files included in file-level AI summarization
- `ENABLE_SPLIT_SUGGESTION`: enable split-commit recommendation
- `SPLIT_CONFIDENCE_THRESHOLD`: minimum AI confidence to show split recommendation
- `DIFF_SUMMARY_CONCURRENCY`: concurrent file-summary requests
- `RETRY_MAX_ATTEMPTS`: max attempts when provider hits rate limit (runtime minimum: 5)
- `RETRY_BASE_DELAY_SECONDS`: initial backoff delay for rate-limit retry (runtime minimum: 2.0s)
- `RETRY_MAX_DELAY_SECONDS`: max backoff delay for rate-limit retry (runtime minimum: 30.0s)

## 🔁 Retry and Fallback Behavior

- CMAI retries only on likely rate-limit errors (such as `429`, `RPM limit`, `too many requests`, `limit exceeded`).
- Backoff uses exponential delays with an extra scale factor: `base * 2^(attempt-1) * 1.5`, capped by `RETRY_MAX_DELAY_SECONDS`.
- If retries are exhausted for final commit generation, CMAI builds a local commit message that still follows your configured commit rules.

## 📦 Development

```bash
git clone [https://github.com/yumuzhihan/cmai.git](https://github.com/yumuzhihan/cmai.git)
cd cmai
uv sync --all-extras    # Or other groups
python -m pytest        # Run tests
```

## 📄 License

This project is licensed under the [MIT License](https://github.com/yumuzhihan/cmai/blob/main/LICENSE).
