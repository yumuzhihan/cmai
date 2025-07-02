# CMAI - AI-Powered Commit Message Normalizer

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

CMAI is an intelligent command-line tool that leverages AI to transform informal or colloquial commit messages into standardized, professional Git commit messages. It analyzes your staged changes and uses advanced language models to generate clear, concise, and conventional commit messages.

## 🌟 Features

- **AI-Powered Normalization**: Converts informal commit descriptions into professional, standardized commit messages
- **Git Integration**: Automatically analyzes staged changes to provide context-aware suggestions
- **Multiple AI Provider Support**: Currently supports Bailian (Qwen) models with extensible architecture for additional providers
- **Configurable**: Customizable prompt templates and model settings
- **Token Usage Tracking**: Monitor AI token consumption for cost management
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## 🚀 Quick Start

### Installation

Install CMAI using pip:

```bash
pip install cmai
```

Or install from source:

```bash
git clone https://github.com/yumuzhihan/cmai.git
cd cmai
pip install -e .
```

### Basic Usage

1. Stage your changes in Git:

```bash
git add .
```

2. Use CMAI to generate a normalized commit message:

```bash
cmai "fix some bugs in user authentication"
```

3. The tool will output a standardized commit message like:

```text
Commit message: Fix authentication bugs in user login module
Tokens used: 45
```

## 🔧 Configuration

CMAI uses a configuration file located at `~/.config/cmai/settings.env`. The configuration file will be automatically created on first run.

### Environment Variables

Create or edit `~/.config/cmai/settings.env`:

```env
# AI Provider Configuration
PROVIDER=openai
API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key_here
MODEL=qwen-turbo-latest

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE_PATH=/path/to/logfile.log

# Prompt Template (optional customization)
PROMPT_TEMPLATE=Please generate a standardized commit message based on the user description: {user_input}. The changes include: {diff_content}. Respond only with the normalized commit message in English.
```

### API Key Setup

For Bailian (Qwen) models, you can set your API key in several ways:

1. **Environment variable** (recommended):

```bash
export DASHSCOPE_API_KEY=your_api_key_here
```

2. **Configuration file**: Add `API_KEY=your_api_key_here` to `~/.config/cmai/settings.env`

3. **Custom config file**: Use the `--config` option to specify a different configuration file

## 📖 Usage Examples

### Command Examples

```bash
# Simple commit message normalization
cmai "updated readme file"
# Output: Update README documentation
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
  -c, --config TEXT  Path to configuration file
  -r, --repo TEXT    Git repository path
  --help            Show this message and exit
```

## 🏗️ Architecture

CMAI follows a modular architecture with the following components:

### Core Components

- **`cmai.main`**: Entry point and CLI interface using Click
- **`cmai.core.normalizer`**: Core logic for commit message normalization
- **`cmai.core.get_logger`**: Logging factory and configuration
- **`cmai.config.settings`**: Configuration management using Pydantic

### Provider System

- **`cmai.providers.base`**: Abstract base class for AI providers
- **`cmai.providers.bailian_provider`**: Bailian (Qwen) AI implementation
- Extensible design allows for easy addition of new AI providers

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

## 🔌 Extending CMAI

### Adding New AI Providers

To add support for a new AI provider, create a class that inherits from `BaseAIClient`:

```python
from cmai.providers.base import BaseAIClient, AIResponse

class CustomProvider(BaseAIClient):
    async def normalize_commit(self, prompt: str, **kwargs) -> AIResponse:
        # Implement your provider logic here
        pass
    
    def validate_config(self) -> bool:
        # Implement configuration validation
        pass
```

### Custom Prompt Templates

You can customize the prompt template by modifying the `PROMPT_TEMPLATE` setting:

```env
PROMPT_TEMPLATE=Custom prompt: {user_input}. Context: {diff_content}. Generate a commit message.
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

2. Create a virtual environment:

```bash
uv venv

# Activate virtual environment
# On Unix/macOS:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

3. Install development dependencies:

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
│   │   └── bailian_provider.py  # Bailian implementation
│   └── utils/
│       ├── __init__.py
│       └── git_staged_analyzer.py  # Git utilities
├── tests/                   # Test suite
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
├── pyproject.toml          # Project configuration
├── LICENSE                 # AGPL-3.0 License
└── README.md              # This file
```

### Running Tests

```bash
python -m pytest tests/
```

## 📋 Requirements

- Python 3.12 or higher
- Git (for repository analysis)
- Internet connection (for AI provider APIs)

### Dependencies

- `click>=8.2.1` - Command-line interface
- `openai>=1.91.0` - OpenAI-compatible API client
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

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for the CLI interface
- Uses [Pydantic](https://pydantic.dev/) for configuration and data validation
- Integrates with [Bailian API](https://bailian.console.aliyun.com/) for AI functionality
- Inspired by conventional commit standards

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yumuzhihan/cmai/issues) page
2. Create a new issue with detailed information
3. Review the documentation and configuration guide

---

**Note**: This tool requires API access to AI language models. Please ensure you have appropriate API keys and understand the associated costs before using CMAI in production environments.
