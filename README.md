# CMAI - AI-Powered Commit Message Normalizer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

CMAI is an intelligent command-line tool that leverages AI to transform informal or colloquial commit messages into standardized, professional Git commit messages. It analyzes your staged changes and uses advanced language models to generate clear, concise, and conventional commit messages.

## 🌟 Features

- **AI-Powered Normalization**: Converts informal commit descriptions into professional, standardized commit messages
- **Git Integration**: Automatically analyzes staged changes to provide context-aware suggestions
- **Multiple AI Provider Support**: Supports various AI providers including OpenAI-compatible APIs, Bailian (Qwen), DeepSeek, SiliconFlow, and local Ollama models
- **Extensible Architecture**: Easy to add new AI providers through the provider factory system
- **Configurable**: Customizable prompt templates and model settings
- **Token Usage Tracking**: Monitor AI token consumption for cost management
- **Comprehensive Logging**: Detailed logging for debugging and monitoring with stream output support

## 🚀 Quick Start

### Installation

Install CMAI using pip, or uv as recommended:

```bash
uv tool install cmai # Just the core package, without any provider dependencies, you need to install provider-specific extras separately
uv tool install cmai[openai] # For OpenAI-compatible APIs
uv tool install cmai[ollama] # For Ollama local models
uv tool install cmai[all_providers] # For all supported providers
```

Or install from source:

```bash
git clone https://github.com/yumuzhihan/cmai.git
cd cmai
pip install -e .
```

### Quick Setup

1. **Configure your AI provider** (this step is **required**):

Create `~/.config/cmai/settings.env`:

```env
# Example: Using OpenAI
PROVIDER=openai
API_KEY=your_openai_api_key
MODEL=gpt-4o-mini

# Or using Ollama locally
# PROVIDER=ollama
# OLLAMA_HOST=http://localhost:11434
# MODEL=qwen2.5:7b
```

1. **Set your API key** (if using remote providers):

```bash
# For OpenAI
export CMAI_API_KEY=your_api_key

# For Bailian
export CMAI_API_KEY=your_api_key

# For DeepSeek
export CMAI_API_KEY=your_api_key

# For SiliconFlow
export CMAI_API_KEY=your_api_key

# For Ollama, no API key is needed

# For Zai (智谱AI)
export CMAI_API_KEY=your_api_key
```

1. **Test the installation**:

```bash
# Stage some changes
git add .

# Generate a commit message
cmai "fixed a bug"
```

### Basic Usage

1. Stage your changes in Git:

```bash
git add .
```

1. Use CMAI to generate a normalized commit message:

```bash
cmai "fix some bugs in user authentication"
```

1. The tool will output a standardized commit message like:

```text
Commit message: Fix authentication bugs in user login module
Tokens used: 45
Elapsed time: 38.94 seconds

Action ([c]ommit / [e]dit / [a]bort) (c, e, a) [c]:
```

You can then choose to commit, edit, or abort the operation.

**Note:** If you use Zai (智谱AI) as your provider, the token usage will not be provided due to API limitations. So the output tokens usage will be displayed as `0`.

⚠️ **Important Setup Reminder**: Before using CMAI, you must configure at least two settings:

- `PROVIDER`: The AI provider you want to use (e.g., `openai`, `bailian`, `ollama`)
- `MODEL`: The specific model name (this is **required** for all providers)

Without these configurations, CMAI will fail to run. And most providers require an API key. See the [Configuration](#-configuration) section for details.

## 🔧 Configuration

CMAI uses a configuration file located at `~/.config/cmai/settings.env`. The configuration file will be automatically created on first run.

### Environment Variables

Create or edit `~/.config/cmai/settings.env`:

```env
# AI Provider Configuration
PROVIDER=openai
# If API_BASE is not specified, the default base URL of `openai` sdk will be used
API_BASE=https://api.openai.com/v1
API_KEY=your_api_key_here
MODEL=gpt-4o-mini

# For Bailian (Qwen) API
# PROVIDER=bailian
# API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
# API_KEY=your_dashscope_api_key
# MODEL=qwen-turbo-latest

# For DeepSeek API(Not tested yet)
# PROVIDER=deepseek
# API_BASE=https://api.deepseek.com/v1
# API_KEY=your_deepseek_api_key
# MODEL=deepseek-chat

# For SiliconFlow API
# PROVIDER=siliconflow
# API_BASE=https://api.siliconflow.cn/v1
# API_KEY=your_siliconflow_api_key
# MODEL=Qwen/Qwen2.5-7B-Instruct

# For Ollama (local)
# PROVIDER=ollama
# OLLAMA_HOST=http://localhost:11434
# MODEL=qwen2.5:7b

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE_PATH=/path/to/logfile.log

# Prompt Template (optional customization)
PROMPT_TEMPLATE=Please generate a standardized commit message based on the user description: {user_input}. The changes include: {diff_content}. Respond only with the normalized commit message in English.

# Token Usage Limit (optional)
DIFF_LENGTH_LIMIT=10000 # Maximum length of diff content to consider, if exceeded, it will only provide a list of the modified files.
```

### Supported AI Providers

CMAI supports multiple AI providers through its extensible architecture:

#### 1. OpenAI-Compatible APIs

- **OpenAI**: Official OpenAI API
- **Bailian (Qwen)**: Alibaba Cloud's Qwen models
- **DeepSeek**: DeepSeek's AI models
- **SiliconFlow**: SiliconFlow's AI services
- **ChatGPT**: OpenAI ChatGPT models
- **Zai (智谱AI)**: Zai's large language models, such as GLM series

#### 2. Local Models

- **Ollama**: Run models locally using Ollama

### Important: Model Configuration

⚠️ **Important**: You must specify a `MODEL` in your configuration. CMAI requires an explicit model name to function properly. Examples:

- OpenAI: `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`
- Bailian: `qwen-turbo-latest`, `qwen-plus-latest`, `qwen-max-latest`
- DeepSeek: `deepseek-chat`, `deepseek-coder`
- SiliconFlow: `Qwen/Qwen2.5-7B-Instruct`, `deepseek-ai/DeepSeek-V2.5`
- Ollama: `qwen2.5:7b`, `llama3.1:8b`, `codellama:7b`
- Zai: `glm-4.5-flash`, `glm-4-0520-bolt`

### API Key Setup

Different providers require different API keys, and there are two ways to set them up:

- **Environment Variable**: Set the `CMAI_API_KEY` environment variable in your shell, and use `cmai` command in the same shell session. The toll will try to extract the API key from the environment variable.

```bash
export CMAI_API_KEY=your_api_key_here
```

- **Configuration File**: Set the `API_KEY` in the `~/.config/cmai/settings.env` file. You can also specify the config file path using the `--config`(or `-c`) option.

```env
API_KEY=your_api_key_here
```

## 📖 Usage Examples

### Usage Examples

```bash
# Simple commit message normalization (uses configuration file settings)
cmai "updated readme file"

# Using a custom configuration file
cmai "fixed authentication bug" --config /path/to/custom/config.env

# Specifying a different repository
cmai "refactored user service" --repo /path/to/repo
```

### Using Custom Configuration

```bash
# Use a specific configuration file
cmai "refactored auth system" --config /path/to/custom/config.env
```

### Specifying Repository Path

```bash
# Analyze changes in a specific repository
cmai "fixed login bug" --repo /path/to/your/repo
```

### Full Command Options

```bash
cmai [OPTIONS] MESSAGE

Arguments:
  MESSAGE  The informal commit message to be normalized [required]

Options:
  -c, --config TEXT     Path to configuration file
  -r, --repo TEXT       Git repository path
  -l, --language TEXT   Language for the resulting commit message. It will be passed to the llm by prompt,
                        e.g., "English", "Chinese", etc.
  --help                Show this message and exit
```

**Note**: Provider and model selection is configured through the configuration file or environment variables, not command-line arguments.

### Configuration Examples for Different Providers

To use different AI providers, configure your `~/.config/cmai/settings.env` file:

#### OpenAI

```env
PROVIDER=openai
API_BASE=https://api.openai.com/v1
API_KEY=your_openai_api_key
MODEL=gpt-4o-mini
```

#### Bailian (Qwen)

```env
PROVIDER=bailian
API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_dashscope_api_key
MODEL=qwen-turbo-latest
```

#### DeepSeek

```env
PROVIDER=deepseek
API_BASE=https://api.deepseek.com/v1
API_KEY=your_deepseek_api_key
MODEL=deepseek-chat
```

#### SiliconFlow

```env
PROVIDER=siliconflow
API_BASE=https://api.siliconflow.cn/v1
API_KEY=your_siliconflow_api_key
MODEL=Qwen/Qwen2.5-7B-Instruct
```

#### Ollama (Local)

```env
PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
MODEL=qwen2.5:7b
```

#### Zai (智谱AI)

```env
PROVIDER=zai
API_BASE=https://open.bigmodel.cn/api/paas/v4/
API_KEY=your_zhipu_api_key
MODEL=glm-4.5-flash
```

After configuring your preferred provider, simply use:

```bash
cmai "your commit message"
```

## 🏗️ Architecture

CMAI follows a modular architecture with the following components:

### Core Components

- **`cmai.main`**: Entry point and CLI interface using Click
- **`cmai.core.normalizer`**: Core logic for commit message normalization
- **`cmai.core.get_logger`**: Logging factory and configuration with stream support
- **`cmai.config.settings`**: Configuration management using Pydantic

### Provider System

- **`cmai.providers.base`**: Abstract base class for AI providers
- **`cmai.providers.openai_provider`**: OpenAI-compatible API implementation
- **`cmai.providers.ollama_provider`**: Ollama local model implementation
- **`cmai.providers.provider_factory`**: Factory for creating and managing providers
- **`cmai.providers.zai_provider`**: Zai (智谱AI) provider implementation
- **`cmai.providers.bailian_provider`**: Legacy Bailian provider (deprecated)

### Utilities

- **`cmai.utils.git_staged_analyzer`**: Git repository analysis and diff extraction

### Data Models

```python
class AIResponse(BaseModel):
    content: str           # The normalized commit message
    model: str            # AI model used
    provider: str         # AI provider name
    tokens_used: Optional[int]  # Token consumption
```

### Provider Factory System

CMAI uses a factory pattern for managing AI providers:

```python
from cmai.providers.provider_factory import create_provider

# Create provider with default settings
provider = create_provider()

# Create specific provider with model
provider = create_provider("openai", model="gpt-4o-mini")

# Create Ollama provider
provider = create_provider("ollama", model="qwen2.5:7b")
```

## 🔌 Extending CMAI

### Adding New AI Providers

To add support for a new AI provider, create a class that inherits from `BaseAIClient` and register it with the provider factory:

```python
from cmai.providers.base import BaseAIClient, AIResponse
from cmai.providers.provider_factory import register_custom_provider

class CustomProvider(BaseAIClient):
    async def normalize_commit(self, prompt: str, **kwargs) -> AIResponse:
        # Implement your provider logic here
        # Must return AIResponse with content, model, provider, and tokens_used
        pass
    
    def validate_config(self) -> bool:
        # Implement configuration validation
        return True

# Register the provider
register_custom_provider("custom", CustomProvider)
```

### Using the Provider Factory

The provider factory automatically manages different AI providers:

```python
from cmai.providers.provider_factory import (
    create_provider,
    list_available_providers,
    register_custom_provider
)

# List all available providers
providers = list_available_providers()
print(providers)
# Output: {'openai': 'OpenaiProvider', 'ollama': 'OllamaProvider', ...}

# Create provider instances
openai_provider = create_provider("openai", model="gpt-4o-mini")
ollama_provider = create_provider("ollama", model="qwen2.5:7b")
```

### Custom Prompt Templates

You can customize the prompt template by modifying the `PROMPT_TEMPLATE` setting:

```env
PROMPT_TEMPLATE=Generate a standardized commit message based on: {user_input}. Changes: {diff_content}. Use conventional commit format.
```

Available placeholders:

- `{user_input}`: The user's informal commit message
- `{diff_content}`: Git diff information from staged changes

## 🛠️ Development

### Setting Up Development Environment

1. Clone the repository:

```bash
git clone https://github.com/yumuzhihan/cmai.git
cd cmai
```

1. Create a virtual environment:

```bash
uv venv

# Activate virtual environment
# On Unix/macOS:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

1. Install development dependencies:

```bash
# Install all dependencies including dev dependencies
uv sync --dev

# Or if you prefer to install only production dependencies:
uv sync
```

### Project Structure

```text
cmai/
├── cmai/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # Configuration management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── get_logger.py    # Logging utilities
│   │   └── normalizer.py    # Core normalization logic
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract provider interface
│   │   ├── openai_provider.py    # OpenAI-compatible implementation
│   │   ├── ollama_provider.py    # Ollama local model implementation
│   │   ├── provider_factory.py   # Provider factory system
│   │   └── bailian_provider.py   # Legacy Bailian provider
│   └── utils/
│       ├── __init__.py
│       └── git_staged_analyzer.py  # Git utilities
├── tests/                   # Test suite
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
├── pyproject.toml          # Project configuration
├── uv.lock                 # UV lock file
├── LICENSE                 # AGPL-3.0 License
└── README.md              # This file
```

### Running Tests

```bash
python -m pytest tests/
```

## 📋 Requirements

- Python 3.10 or higher
- Git (for repository analysis)
- Internet connection (for remote AI provider APIs)
- Ollama installation (for local AI models)

### Dependencies

- `click>=8.2.1` - Command-line interface
- `openai>=1.91.0` - OpenAI-compatible API client
- `ollama>=0.5.1` - Ollama Python client for local models
- `pydantic>=2.11.7` - Data validation and settings
- `pydantic-settings>=2.10.0` - Settings management

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Contribution Guidelines

- Follow PEP 8 coding standards
- Add type hints to all functions
- Write comprehensive tests
- Update documentation for new features
- Ensure backward compatibility
- When adding new providers, register them in the provider factory

### Adding New Providers

When contributing new AI providers:

1. Create a new file in `cmai/providers/` (e.g., `custom_provider.py`)
2. Implement the `BaseAIClient` interface
3. Register the provider in `provider_factory.py`
4. Add configuration examples to the README
5. Include tests for the new provider

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for the CLI interface
- Uses [Pydantic](https://pydantic.dev/) for configuration and data validation
- Supports multiple AI providers including [OpenAI](https://openai.com/), [Bailian](https://bailian.console.aliyun.com/), [DeepSeek](https://www.deepseek.com/), [SiliconFlow](https://siliconflow.cn/), and [Ollama](https://ollama.com/)
- Inspired by conventional commit standards
- Uses [UV](https://docs.astral.sh/uv/) for fast Python package management

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yumuzhihan/cmai/issues) page
2. Create a new issue with detailed information about your setup (provider, model, configuration)
3. Review the documentation and configuration guide
4. For provider-specific issues, include your provider and model information

### Common Issues

- **"Model must be specified"**: Ensure you have set the `MODEL` in your configuration file or passed it as a command-line argument
- **API key errors**: Verify that your API key is correctly set for your chosen provider
- **Connection errors**: Check your internet connection and API endpoint URLs
- **Ollama connection issues**: Ensure Ollama is running locally and accessible at the configured host

---

**Note**: This tool requires access to AI language models. Please ensure you have appropriate API keys and understand the associated costs before using CMAI in production environments. For local usage, consider using Ollama with open-source models.
