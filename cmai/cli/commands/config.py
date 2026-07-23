"""Interactive management for CMAI's global configuration file."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

import click

from cmai.config.settings import (
    DEFAULT_PROMPT_TEMPLATE,
    DEFAULT_SETTINGS_PATH,
    PROMPT_TEMPLATE_VARIABLES,
    Settings,
    encode_prompt_template,
    has_legacy_prompt_template_variables,
    has_required_prompt_template_variables,
    normalize_prompt_template_variables,
    settings,
)
from cmai.core.commit_spec import resolve_commit_rules
from cmai.providers.provider_factory import ProviderFactory

PROVIDER_KEYS = ("PROVIDER", "API_BASE", "API_KEY", "MODEL", "OLLAMA_HOST")
COMMIT_KEYS = (
    "COMMIT_STRICT",
    "COMMIT_SPEC",
    "COMMIT_ALLOWED_TYPES",
    "COMMIT_SCOPE_POLICY",
    "COMMIT_SUBJECT_MAX_LEN",
    "COMMIT_HEADER_MAX_LEN",
    "COMMIT_SUBJECT_CASE",
    "COMMIT_ALLOW_BANG",
)
OPTIONAL_KEYS = ("PROMPT_TEMPLATE", "RESPONSE_LANGUAGE")
MANAGED_KEYS = PROVIDER_KEYS + COMMIT_KEYS + OPTIONAL_KEYS

CLEARABLE_KEYS = {"API_BASE", "API_KEY", "MODEL", "OLLAMA_HOST", "COMMIT_ALLOWED_TYPES"}
_MISSING = object()
_KEEP = object()
_ENV_ASSIGNMENT = re.compile(
    r"^(?P<leading>\s*)(?:(?P<export>export)\s+)?"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<before_equals>\s*)="
    r"(?P<value>.*?)(?P<newline>\r?\n)?$"
)
_SAFE_ENV_VALUE = re.compile(r"^[A-Za-z0-9._:/@+=,%-]+$")
_COMMIT_TYPE = re.compile(r"^[a-z]+$")


class EnvFileError(ValueError):
    """Raised when a dotenv file cannot be safely read or updated."""


@dataclass(frozen=True)
class ConfigDocument:
    path: Path
    exists: bool
    lines: tuple[str, ...]
    values: Mapping[str, str]
    current: Settings


def _split_inline_comment(value: str) -> tuple[str, str]:
    """Split a dotenv value from a trailing comment without touching quoted #."""

    stripped = value.strip()
    if not stripped:
        return "", ""

    if stripped[0] in {"'", '"'}:
        quote = stripped[0]
        escaped = False
        for index, char in enumerate(stripped[1:], start=1):
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char == quote and not escaped:
                suffix = stripped[index + 1 :].strip()
                return stripped[: index + 1], suffix if suffix.startswith("#") else ""
            escaped = False
        return stripped, ""

    comment_match = re.search(r"\s+(#.*)$", stripped)
    if comment_match:
        return stripped[: comment_match.start()].rstrip(), comment_match.group(1)
    return stripped, ""


def _parse_env_value(value: str, *, path: Path, line_number: int) -> str:
    raw_value, _ = _split_inline_comment(value)
    if not raw_value:
        return ""

    if raw_value[0] == '"':
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise EnvFileError(
                f"Invalid quoted value at {path}:{line_number}: {error.msg}."
            ) from error
        if not isinstance(parsed, str):
            raise EnvFileError(
                f"Invalid quoted value at {path}:{line_number}: expected a string."
            )
        return parsed

    if raw_value[0] == "'":
        if len(raw_value) < 2 or not raw_value.endswith("'"):
            raise EnvFileError(f"Unterminated quoted value at {path}:{line_number}.")
        return raw_value[1:-1]

    return raw_value


def read_env_file(path: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    """Read a conservative single-line dotenv format while retaining source lines."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise EnvFileError(f"Cannot read {path}: {error.strerror or error}.") from error

    lines = tuple(text.splitlines(keepends=True))
    values: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _ENV_ASSIGNMENT.match(line)
        if not match:
            raise EnvFileError(
                f"Malformed dotenv entry at {path}:{line_number}; expected KEY=value."
            )
        key = match.group("key")
        values[key] = _parse_env_value(
            match.group("value"), path=path, line_number=line_number
        )
    return lines, values


def _serialize_env_value(key: str, value: Any) -> str:
    if key == "PROMPT_TEMPLATE":
        return encode_prompt_template(str(value))
    if isinstance(value, bool):
        return "true" if value else "false"

    text = str(value)
    if text and _SAFE_ENV_VALUE.fullmatch(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _comparable_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _validate_updates(updates: Mapping[str, Any]) -> None:
    unknown_keys = set(updates).difference(MANAGED_KEYS)
    if unknown_keys:
        joined = ", ".join(sorted(unknown_keys))
        raise ValueError(f"Only managed settings can be changed: {joined}.")

    for key, value in updates.items():
        if value is None:
            if key not in CLEARABLE_KEYS:
                raise ValueError(f"{key} cannot be empty.")
            continue

        if key == "API_KEY":
            if (
                not isinstance(value, str)
                or not value.strip()
                or "\n" in value
                or "\r" in value
            ):
                raise ValueError("API key must be a non-empty single-line value.")
        elif key == "PROMPT_TEMPLATE":
            if not isinstance(value, str) or not has_required_prompt_template_variables(
                value
            ):
                variables = ", ".join(PROMPT_TEMPLATE_VARIABLES)
                raise ValueError(f"Prompt template must include {variables}.")
        elif key == "RESPONSE_LANGUAGE":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Response language must not be empty.")
        elif isinstance(value, str) and ("\n" in value or "\r" in value):
            raise ValueError(f"{key} must be a single-line value.")


def merge_managed_settings(
    lines: tuple[str, ...], updates: Mapping[str, Any]
) -> tuple[str, tuple[str, ...]]:
    """Merge managed values into dotenv text without rewriting unrelated content."""

    _validate_updates(updates)
    _, existing_values = _parse_lines_for_merge(lines)

    changed: list[str] = []
    for key, desired in updates.items():
        current = existing_values.get(key, _MISSING)
        if desired is None:
            if current is not _MISSING:
                changed.append(key)
        elif current is _MISSING or _comparable_value(current) != _comparable_value(
            desired
        ):
            changed.append(key)

    if not changed:
        return "".join(lines), ()

    changed_set = set(changed)
    handled: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = _ENV_ASSIGNMENT.match(line)
        if not match or match.group("key") not in changed_set:
            output.append(line)
            continue

        key = match.group("key")
        if key in handled:
            # A changed managed setting gets one canonical entry; all duplicate
            # definitions are removed so a later dotenv reader cannot override it.
            continue
        handled.add(key)

        value = updates[key]
        if value is None:
            continue

        _, inline_comment = _split_inline_comment(match.group("value"))
        newline = match.group("newline") or "\n"
        comment_suffix = f" {inline_comment}" if inline_comment else ""
        output.append(
            f"{match.group('leading')}{key}={_serialize_env_value(key, value)}"
            f"{comment_suffix}{newline}"
        )

    content = "".join(output)
    if content and not content.endswith(("\n", "\r")):
        content += "\n"
    for key in MANAGED_KEYS:
        if key not in changed_set or key in handled or updates[key] is None:
            continue
        content += f"{key}={_serialize_env_value(key, updates[key])}\n"

    return content, tuple(changed)


def _parse_lines_for_merge(
    lines: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Parse in-memory source lines with the same safety rules as ``read_env_file``."""

    values: dict[str, str] = {}
    synthetic_path = Path("settings.env")
    for line_number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _ENV_ASSIGNMENT.match(line)
        if not match:
            raise EnvFileError(
                f"Malformed dotenv entry at line {line_number}; expected KEY=value."
            )
        values[match.group("key")] = _parse_env_value(
            match.group("value"), path=synthetic_path, line_number=line_number
        )
    return lines, values


def atomic_write_env_file(path: Path, content: str) -> None:
    """Atomically replace the configuration file and restrict POSIX permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def save_managed_settings(path: Path, updates: Mapping[str, Any]) -> tuple[str, ...]:
    """Apply settings atomically and refresh the shared in-memory settings object."""

    if path.exists():
        lines, _ = read_env_file(path)
    else:
        lines = ()
    content, changed = merge_managed_settings(lines, updates)
    if not changed:
        return changed

    atomic_write_env_file(path, content)
    settings.load_from_env(path)
    return changed


def load_config_document(path: Path) -> ConfigDocument:
    exists = path.exists()
    if exists:
        lines, values = read_env_file(path)
    else:
        lines, values = (), {}

    try:
        current = Settings.from_env_file(path)
    except Exception as error:
        raise EnvFileError(f"Cannot load settings from {path}: {error}.") from error

    return ConfigDocument(
        path=path,
        exists=exists,
        lines=lines,
        values=values,
        current=current,
    )


def _display_value(value: Any, *, empty: str = "not set") -> str:
    return str(value) if value not in (None, "") else empty


def mask_secret(value: str | None) -> str:
    if not value:
        return "not set"
    return "configured (hidden)"


def _show_current_status(document: ConfigDocument) -> None:
    current = document.current
    click.echo(f"Configuration file: {document.path}")
    click.echo(f"Provider: {_display_value(current.PROVIDER)}")
    click.echo(f"API base: {_display_value(current.API_BASE, empty='SDK default')}")
    click.echo(f"API key: {mask_secret(current.API_KEY)}")
    click.echo(f"Model: {_display_value(current.MODEL, empty='SDK default')}")
    click.echo(
        f"Commit: {current.COMMIT_SPEC}, strict={'on' if current.COMMIT_STRICT else 'off'}"
    )
    click.echo(f"Response language: {_display_value(current.RESPONSE_LANGUAGE)}")
    template_kind = (
        "built-in default"
        if current.PROMPT_TEMPLATE == DEFAULT_PROMPT_TEMPLATE
        else "custom"
    )
    click.echo(
        f"Prompt template: {template_kind} ({len(current.PROMPT_TEMPLATE)} characters)"
    )


def _provider_defaults(
    provider: str, providers: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """Expose known SDK defaults without keeping a duplicate provider selection list."""

    provider_class = providers.get(provider, "")
    if provider_class == "OllamaProvider":
        return "http://localhost:11434", "qwen3:8b"
    if provider_class == "AnthropicProvider":
        return None, "claude-3-5-sonnet-20241022"
    if provider_class == "ZhipuAiProvider":
        return None, "glm-4.5-flash"
    return None, "qwen-turbo-latest"


def _prompt_clearable_text(
    label: str,
    *,
    current: str | None,
    default: str | None = None,
    hidden: bool = False,
) -> str | None | object:
    """Prompt provider values while allowing a secure no-change path for API keys."""

    if hidden:
        click.echo(
            f"{label}: {mask_secret(current)}. Press Enter to keep it; type '-' to clear it."
        )
        entered = click.prompt(label, default="", show_default=False, hide_input=True)
        if not entered:
            return _KEEP if current else None
    else:
        initial = current or default
        if initial:
            entered = click.prompt(
                f"{label} (Enter keeps current; '-' clears)",
                default=initial,
                show_default=True,
            )
        else:
            entered = click.prompt(
                f"{label} (optional; '-' clears)", default="", show_default=False
            )

    if entered == "-":
        return None
    if not entered:
        return None
    if "\n" in entered or "\r" in entered:
        raise click.ClickException(f"{label} must be a single-line value.")
    return entered.strip()


def _edit_provider(current: Settings) -> dict[str, Any]:
    factory = ProviderFactory()
    providers = factory.list_providers()
    if not providers:
        raise click.ClickException(
            "No AI providers are available. Install a provider extra, for example "
            "`pip install 'cmai[openai]'`, then run `cmai config` again."
        )

    names = sorted(providers)
    default_provider = (
        current.PROVIDER.lower() if current.PROVIDER.lower() in providers else names[0]
    )
    provider = click.prompt(
        "Provider",
        type=click.Choice(names, case_sensitive=False),
        default=default_provider,
    ).lower()
    default_base, default_model = _provider_defaults(provider, providers)

    current_base = current.API_BASE
    if providers.get(provider) == "OllamaProvider":
        current_base = current.OLLAMA_HOST or current.API_BASE
    click.echo("API base is optional; use it only for a custom or proxy endpoint.")
    api_base = _prompt_clearable_text(
        "API base", current=current_base, default=default_base
    )
    api_key = _prompt_clearable_text("API key", current=current.API_KEY, hidden=True)
    model = _prompt_clearable_text(
        "Model", current=current.MODEL, default=default_model
    )

    if isinstance(api_key, str) and (
        not api_key.strip() or "\n" in api_key or "\r" in api_key
    ):
        raise click.ClickException("API key must be a non-empty single-line value.")

    updates: dict[str, Any] = {"PROVIDER": provider}
    if api_base is not _KEEP:
        updates["API_BASE"] = api_base
    if api_key is not _KEEP:
        updates["API_KEY"] = api_key
    if model is not _KEEP:
        updates["MODEL"] = model

    if providers.get(provider) == "OllamaProvider":
        # Persist the legacy name alongside API_BASE when this section is edited.
        # This keeps older consumers working while API_BASE remains the uniform UI.
        if api_base is not _KEEP:
            updates["OLLAMA_HOST"] = api_base
    else:
        updates["OLLAMA_HOST"] = None

    return updates


def _default_commit_values(spec: str) -> dict[str, Any]:
    return {
        "COMMIT_ALLOWED_TYPES": None,
        "COMMIT_SCOPE_POLICY": "optional",
        "COMMIT_SUBJECT_MAX_LEN": 100 if spec == "angular" else 72,
        "COMMIT_HEADER_MAX_LEN": 100,
        "COMMIT_SUBJECT_CASE": "lower",
        "COMMIT_ALLOW_BANG": True,
    }


def _prompt_allowed_types(current: str | None) -> str | None:
    current_text = current or "spec default"
    click.echo(f"Allowed commit types currently: {current_text}")
    raw = click.prompt(
        "Allowed types (comma-separated; leave blank for the specification default)",
        default="",
        show_default=False,
    ).strip()
    if not raw:
        return None

    types = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not types or any(not _COMMIT_TYPE.fullmatch(item) for item in types):
        raise click.ClickException(
            "Allowed types must be comma-separated lowercase words, for example feat,fix,docs."
        )
    return ",".join(dict.fromkeys(types))


def _show_commit_rules(current: Settings, updates: Mapping[str, Any]) -> None:
    candidate = current.model_copy(deep=True)
    for key, value in updates.items():
        setattr(candidate, key, value)
    rules = resolve_commit_rules(candidate)
    click.echo("Commit rule summary:")
    click.echo(f"  Specification: {rules.spec}")
    click.echo(f"  Strict mode: {'on' if candidate.COMMIT_STRICT else 'off'}")
    click.echo(f"  Allowed types: {', '.join(rules.allowed_types)}")
    click.echo(
        f"  Scope: {rules.scope_policy}; subject/header limit: {rules.subject_max_len}/{rules.header_max_len}"
    )
    click.echo(
        f"  Subject case: {rules.subject_case}; bang allowed: {'yes' if rules.allow_bang else 'no'}"
    )


def _edit_commit(current: Settings) -> dict[str, Any]:
    strict = click.confirm(
        "Enable strict commit validation", default=current.COMMIT_STRICT
    )
    spec = click.prompt(
        "Commit specification",
        type=click.Choice(["conventional", "angular"], case_sensitive=False),
        default=(current.COMMIT_SPEC or "conventional").lower(),
    ).lower()
    mode = click.prompt(
        "Commit rules",
        type=click.Choice(["default", "detailed"], case_sensitive=False),
        default="default",
    ).lower()

    updates: dict[str, Any] = {"COMMIT_STRICT": strict, "COMMIT_SPEC": spec}
    if mode == "default":
        updates.update(_default_commit_values(spec))
    else:
        updates["COMMIT_ALLOWED_TYPES"] = _prompt_allowed_types(
            current.COMMIT_ALLOWED_TYPES
        )
        updates["COMMIT_SCOPE_POLICY"] = click.prompt(
            "Scope policy",
            type=click.Choice(["optional", "required", "forbid"], case_sensitive=False),
            default=current.COMMIT_SCOPE_POLICY,
        ).lower()
        updates["COMMIT_SUBJECT_MAX_LEN"] = click.prompt(
            "Maximum subject length",
            type=click.IntRange(min=1),
            default=current.COMMIT_SUBJECT_MAX_LEN,
        )
        updates["COMMIT_HEADER_MAX_LEN"] = click.prompt(
            "Maximum header length",
            type=click.IntRange(min=1),
            default=current.COMMIT_HEADER_MAX_LEN,
        )
        updates["COMMIT_SUBJECT_CASE"] = click.prompt(
            "Subject case",
            type=click.Choice(["lower", "sentence", "any"], case_sensitive=False),
            default=current.COMMIT_SUBJECT_CASE,
        ).lower()
        updates["COMMIT_ALLOW_BANG"] = click.confirm(
            "Allow breaking-change bang (!)", default=current.COMMIT_ALLOW_BANG
        )

    _show_commit_rules(current, updates)
    return updates


def _edit_optional(current: Settings) -> dict[str, Any]:
    language = click.prompt(
        "Response language", default=current.RESPONSE_LANGUAGE, show_default=True
    ).strip()
    if not language:
        raise click.ClickException("Response language must not be empty.")

    action = click.prompt(
        "Prompt template",
        type=click.Choice(["keep", "default", "edit"], case_sensitive=False),
        default="keep",
    ).lower()
    updates: dict[str, Any] = {"RESPONSE_LANGUAGE": language}

    if action == "default":
        updates["PROMPT_TEMPLATE"] = DEFAULT_PROMPT_TEMPLATE
        return updates
    if action == "keep":
        return updates

    template = current.PROMPT_TEMPLATE
    if has_legacy_prompt_template_variables(template):
        click.echo("The current template uses legacy double-brace variables.")
        if not click.confirm(
            "Migrate it to the current variable format before editing", default=True
        ):
            click.echo("Template left unchanged.")
            return updates
        template = normalize_prompt_template_variables(template)

    try:
        edited = click.edit(template, extension=".txt")
    except (OSError, click.ClickException) as error:
        click.echo(f"Could not open an editor ({error}); template left unchanged.")
        return updates

    if edited is None or edited == template:
        click.echo("Template was not changed.")
        return updates
    if not has_required_prompt_template_variables(edited):
        variables = ", ".join(PROMPT_TEMPLATE_VARIABLES)
        raise click.ClickException(f"Prompt template must include {variables}.")

    updates["PROMPT_TEMPLATE"] = normalize_prompt_template_variables(edited)
    return updates


def _preview_updates(path: Path, updates: Mapping[str, Any]) -> None:
    click.echo()
    click.echo(f"Changes to save in {path}:")
    for key in MANAGED_KEYS:
        if key not in updates:
            continue
        value = updates[key]
        if key == "API_KEY":
            rendered = "will be cleared" if value is None else "updated (hidden)"
        elif key == "PROMPT_TEMPLATE":
            rendered = f"custom template ({len(str(value))} characters)"
        elif value is None:
            rendered = "will be cleared"
        else:
            rendered = str(value)
        click.echo(f"  {key}: {rendered}")


def _run_configuration(path: Path) -> None:
    document = load_config_document(path)
    updates: dict[str, Any]

    if not document.exists:
        click.echo(f"No global configuration exists at {path}.")
        click.echo(
            "Starting the complete configuration wizard. Nothing is written until you confirm."
        )
        updates = {}
        updates.update(_edit_provider(document.current))
        updates.update(_edit_commit(document.current))
        updates.update(_edit_optional(document.current))
    else:
        _show_current_status(document)
        click.echo("1. Full reconfiguration")
        click.echo("2. Provider")
        click.echo("3. Commit rules")
        click.echo("4. Optional settings")
        click.echo("5. Exit without saving")
        choices = {
            "1": "full",
            "2": "provider",
            "3": "commit",
            "4": "optional",
            "5": "exit",
            # Descriptive aliases keep scripted Click invocations readable.
            "full": "full",
            "provider": "provider",
            "commit": "commit",
            "optional": "optional",
            "exit": "exit",
        }
        choice = click.prompt(
            "Choose section",
            type=click.Choice(list(choices), case_sensitive=False),
            default="5",
        ).lower()
        choice = choices[choice]
        if choice == "exit":
            click.echo("Configuration unchanged.")
            return
        if choice == "full":
            updates = {}
            updates.update(_edit_provider(document.current))
            updates.update(_edit_commit(document.current))
            updates.update(_edit_optional(document.current))
        elif choice == "provider":
            updates = _edit_provider(document.current)
        elif choice == "commit":
            updates = _edit_commit(document.current)
        else:
            updates = _edit_optional(document.current)

    _preview_updates(path, updates)
    if not click.confirm("Save these changes", default=True):
        click.echo("Configuration cancelled; no changes were saved.")
        return

    try:
        changed = save_managed_settings(path, updates)
    except (OSError, ValueError, EnvFileError) as error:
        raise click.ClickException(
            f"Could not save configuration at {path}: {error}"
        ) from error

    if not changed:
        click.echo("No settings changed; no file was written.")
        return
    click.echo(f"Saved configuration to {path}.")
    click.echo(f"Updated: {', '.join(changed)}.")
    click.echo("The new settings will be used the next time you run cmai.")


@click.command("config")
def config_command() -> None:
    """Interactively manage the global CMAI configuration."""

    try:
        _run_configuration(DEFAULT_SETTINGS_PATH)
    except EnvFileError as error:
        raise click.ClickException(str(error)) from error
    except (click.Abort, KeyboardInterrupt) as error:
        raise click.ClickException(
            "Configuration cancelled; no changes were saved. Run cmai config in an interactive terminal."
        ) from error
