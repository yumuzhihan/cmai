import asyncio
import json
import subprocess
import time
from typing import Optional

import click

from cmai.cli.ui.commit import (
    display_generation_result,
    edit_message,
    prompt_action,
    prompt_additional_prompt,
    prompt_large_diff_mode,
    show_commit_aborted,
    show_commit_failure,
    show_commit_success,
    show_validation_warning,
)
from cmai.config.settings import settings
from cmai.core.commit_spec import resolve_commit_rules
from cmai.core.commit_validator import validate_commit_message
from cmai.core.logger_factory import LoggerFactory
from cmai.core.normalizer import Normalizer
from cmai.providers.base import AIResponse
from cmai.utils.git_staged_analyzer import GitStagedAnalyzer


def _get_logger():
    """Create the persistent logger only when commit generation actually runs."""

    return LoggerFactory().get_logger("CMAI")


async def normalize_commit_async(
    message: str,
    config: Optional[str] = None,
    repo: Optional[str] = None,
    language: Optional[str] = None,
    previous_message: Optional[str] = None,
    validation_errors: Optional[list[str]] = None,
    additional_prompt: Optional[str] = None,
    use_file_summary_for_large_diff: Optional[bool] = None,
) -> AIResponse:
    logger = _get_logger()
    if config:
        settings.load_from_env(config)

    config_dict = settings.model_dump()
    if "API_BASE" in config_dict:
        config_dict["API_BASE"] = "***"
    if "API_KEY" in config_dict:
        config_dict["API_KEY"] = "***"
    logger.debug(f"Using configuration: {json.dumps(config_dict, indent=2)}")
    logger.info(f"Normalizing commit message: {message}")

    normalizer = Normalizer()
    try:
        return await normalizer.normalize_commit(
            user_input=message,
            prompt_template=settings.PROMPT_TEMPLATE,
            repo_path=repo,
            language=language,
            previous_message=previous_message,
            validation_errors=validation_errors,
            additional_prompt=additional_prompt,
            use_file_summary_for_large_diff=use_file_summary_for_large_diff,
        )
    except Exception as e:
        logger.error(f"Error normalizing commit message: {e}")
        raise click.ClickException(f"Failed to normalize commit message: {e}")


class CommitSession:
    def run(
        self,
        message: str,
        config: Optional[str] = None,
        repo: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        if config:
            settings.load_from_env(config)

        use_file_summary_for_large_diff = self._resolve_large_diff_mode(repo)
        result, elapsed_time = self._generate_message(
            message=message,
            config=config,
            repo=repo,
            language=language,
            use_file_summary_for_large_diff=use_file_summary_for_large_diff,
        )
        content = result.content

        rules = resolve_commit_rules(settings)
        click.echo()
        display_generation_result(
            content=content,
            token_usage=result.tokens_used,
            elapsed_time=elapsed_time,
            suggest_split=result.suggest_split,
            split_reason=result.split_reason,
            split_groups=result.split_groups or [],
        )

        while True:
            validation = validate_commit_message(content, rules)
            if not validation.valid and settings.COMMIT_STRICT:
                show_validation_warning(validation.errors)

            click.echo()

            strict_invalid = settings.COMMIT_STRICT and not validation.valid
            choice = prompt_action(strict_invalid=strict_invalid).lower()

            if choice == "c":
                if self._commit(content, repo):
                    break
            elif choice == "e":
                edited = edit_message(content)
                if edited is not None:
                    content = edited
            elif choice == "r":
                result, elapsed_time = self._regenerate_message(
                    message=message,
                    content=content,
                    config=config,
                    repo=repo,
                    language=language,
                    validation_errors=list(validation.errors),
                    use_file_summary_for_large_diff=use_file_summary_for_large_diff,
                )
                content = result.content
                click.echo()
                display_generation_result(
                    content=content,
                    token_usage=result.tokens_used,
                    elapsed_time=elapsed_time,
                    suggest_split=result.suggest_split,
                    split_reason=result.split_reason,
                    split_groups=result.split_groups or [],
                    regenerated=True,
                )
            elif choice == "a":
                show_commit_aborted()
                break

    def _resolve_large_diff_mode(self, repo: Optional[str]) -> Optional[bool]:
        analyzer = GitStagedAnalyzer(repo_path=repo)
        staged_entries = analyzer.get_staged_entries()
        if not staged_entries:
            raise click.ClickException("No staged changes found in the repository.")

        _, is_truncated = analyzer.render_prompt_entries(staged_entries)
        if not is_truncated:
            return None

        return prompt_large_diff_mode()

    def _generate_message(
        self,
        *,
        message: str,
        config: Optional[str],
        repo: Optional[str],
        language: Optional[str],
        use_file_summary_for_large_diff: Optional[bool],
    ) -> tuple[AIResponse, float]:
        started_at = time.time()
        result = asyncio.run(
            normalize_commit_async(
                message=message,
                config=config,
                repo=repo,
                language=language,
                use_file_summary_for_large_diff=use_file_summary_for_large_diff,
            )
        )
        return result, time.time() - started_at

    def _regenerate_message(
        self,
        *,
        message: str,
        content: str,
        config: Optional[str],
        repo: Optional[str],
        language: Optional[str],
        validation_errors: list[str],
        use_file_summary_for_large_diff: Optional[bool],
    ) -> tuple[AIResponse, float]:
        additional_prompt = prompt_additional_prompt()
        started_at = time.time()
        result = asyncio.run(
            normalize_commit_async(
                message=message,
                config=config,
                repo=repo,
                language=language,
                previous_message=content,
                validation_errors=validation_errors,
                additional_prompt=additional_prompt,
                use_file_summary_for_large_diff=use_file_summary_for_large_diff,
            )
        )
        return result, time.time() - started_at

    def _commit(self, content: str, repo: Optional[str]) -> bool:
        try:
            subprocess.run(
                ["git", "commit", "-m", content],
                check=True,
                cwd=repo,
            )
            show_commit_success()
            return True
        except subprocess.CalledProcessError:
            show_commit_failure()
            return False
