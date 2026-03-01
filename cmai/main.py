import asyncio
from typing import Optional
import time
import subprocess

import click

from cmai.config.settings import settings
from cmai.core.commit_spec import resolve_commit_rules
from cmai.core.commit_validator import validate_commit_message
from cmai.core.get_logger import LoggerFactory
from cmai.core.normalizer import Normalizer
from cmai.utils.git_staged_analyzer import GitStagedAnalyzer


async def normalize_commit_async(
    message: str,
    config: Optional[str] = None,
    repo: Optional[str] = None,
    language: Optional[str] = None,
    previous_message: Optional[str] = None,
    validation_errors: Optional[list[str]] = None,
    additional_prompt: Optional[str] = None,
    use_file_summary_for_large_diff: Optional[bool] = None,
):
    logger = LoggerFactory().get_logger("CMAI")

    if config:
        settings.load_from_env(config)

    logger.debug(f"Using configuration: {settings.model_dump_json(indent=2)}")
    logger.info(f"Normalizing commit message: {message}")

    normalizer = Normalizer()
    try:
        normalized_message = await normalizer.normalize_commit(
            user_input=message,
            prompt_template=settings.PROMPT_TEMPLATE,
            repo_path=repo,
            language=language,
            previous_message=previous_message,
            validation_errors=validation_errors,
            additional_prompt=additional_prompt,
            use_file_summary_for_large_diff=use_file_summary_for_large_diff,
        )
        return normalized_message
    except Exception as e:
        logger.error(f"Error normalizing commit message: {e}")
        raise click.ClickException(f"Failed to normalize commit message: {e}")


@click.command()
@click.argument("message", type=str, required=True)
@click.option("--config", "-c", help="配置文件路径", default=None, type=str)
@click.option("--repo", "-r", help="Git仓库路径", default=None, type=str)
@click.option("--language", "-l", help="响应语言", default=None, type=str)
def main(
    message: str,
    config: Optional[str] = None,
    repo: Optional[str] = None,
    language: Optional[str] = None,
):
    """将口语化的commit信息规范化"""
    try:
        if config:
            settings.load_from_env(config)

        use_file_summary_for_large_diff: Optional[bool] = None
        analyzer = GitStagedAnalyzer(repo_path=repo)
        staged_entries = analyzer.get_staged_entries()
        if not staged_entries:
            raise click.ClickException("No staged changes found in the repository.")

        _, is_truncated = analyzer.render_prompt_entries(staged_entries)
        if is_truncated:
            click.echo()
            click.echo(
                click.style(
                    "Detected oversized staged diff. Choose context mode for generation:",
                    fg="yellow",
                )
            )
            mode = click.prompt(
                "Mode ([s]ummary per file / [f]ile list only)",
                default="s",
                show_default=True,
                type=click.Choice(["s", "f"], case_sensitive=False),
            )
            use_file_summary_for_large_diff = mode.lower() == "s"

        start_time = time.time()
        result = asyncio.run(
            normalize_commit_async(
                message,
                config,
                repo,
                language,
                use_file_summary_for_large_diff=use_file_summary_for_large_diff,
            )
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        content = result.content
        token_usage = result.tokens_used
        suggest_split = result.suggest_split
        split_reason = result.split_reason
        split_groups = result.split_groups or []

        rules = resolve_commit_rules(settings)

        # 防止输出最后没有换行
        click.echo()
        click.echo(click.style(f"Commit message: {content}", fg="green"))
        click.echo(click.style(f"Tokens used: {token_usage}", fg="blue"))
        click.echo(
            click.style(f"Elapsed time: {elapsed_time:.2f} seconds", fg="yellow")
        )

        if suggest_split:
            click.echo()
            click.echo(
                click.style(
                    "Suggestion: detected potentially independent staged changes. "
                    "Consider splitting into multiple commits.",
                    fg="yellow",
                )
            )
            if split_reason:
                click.echo(click.style(f"Reason: {split_reason}", fg="yellow"))
            for group in split_groups:
                click.echo(click.style(f"- {group}", fg="yellow"))

        # 交互式提交确认循环
        while True:
            validation = validate_commit_message(content, rules)

            if not validation.valid and settings.COMMIT_STRICT:
                click.echo()
                click.echo(
                    click.style(
                        "Warning: generated commit message is not compliant with current commit specification.",
                        fg="yellow",
                    )
                )
                for error in validation.errors:
                    click.echo(click.style(f"- {error}", fg="red"))

            click.echo()

            strict_invalid = settings.COMMIT_STRICT and not validation.valid
            available_actions = (
                ["e", "r", "a"] if strict_invalid else ["c", "e", "r", "a"]
            )
            action_prompt = (
                "Action ([e]dit / [r]egenerate / [a]bort)"
                if strict_invalid
                else "Action ([c]ommit / [e]dit / [r]egenerate / [a]bort)"
            )

            choice = click.prompt(
                action_prompt,
                default="e" if strict_invalid else "c",
                show_default=True,
                type=click.Choice(available_actions, case_sensitive=False),
            )

            if choice.lower() == "c":
                try:
                    subprocess.run(["git", "commit", "-m", content], check=True)
                    click.echo(click.style("Commit successful!", fg="green"))
                    break
                except subprocess.CalledProcessError:
                    click.echo(
                        click.style(
                            "Commit failed. Please fix the issues and try again.",
                            fg="red",
                        )
                    )
            elif choice.lower() == "e":
                edited = click.edit(content)
                if edited:
                    content = edited.strip()
                    click.echo(
                        click.style(f"New commit message: {content}", fg="green")
                    )
                else:
                    click.echo("No changes made.")
            elif choice.lower() == "r":
                additional_prompt = click.prompt(
                    "Additional prompt (optional)",
                    default="",
                    show_default=False,
                ).strip()

                start_time = time.time()
                result = asyncio.run(
                    normalize_commit_async(
                        message,
                        config,
                        repo,
                        language,
                        previous_message=content,
                        validation_errors=list(validation.errors),
                        additional_prompt=additional_prompt,
                        use_file_summary_for_large_diff=use_file_summary_for_large_diff,
                    )
                )
                end_time = time.time()
                elapsed_time = end_time - start_time

                content = result.content
                token_usage = result.tokens_used
                suggest_split = result.suggest_split
                split_reason = result.split_reason
                split_groups = result.split_groups or []

                click.echo()
                click.echo(
                    click.style(f"Regenerated commit message: {content}", fg="green")
                )
                click.echo(click.style(f"Tokens used: {token_usage}", fg="blue"))
                click.echo(
                    click.style(
                        f"Elapsed time: {elapsed_time:.2f} seconds", fg="yellow"
                    )
                )
                if suggest_split:
                    click.echo()
                    click.echo(
                        click.style(
                            "Suggestion: detected potentially independent staged changes. "
                            "Consider splitting into multiple commits.",
                            fg="yellow",
                        )
                    )
                    if split_reason:
                        click.echo(click.style(f"Reason: {split_reason}", fg="yellow"))
                    for group in split_groups:
                        click.echo(click.style(f"- {group}", fg="yellow"))
            elif choice.lower() == "a":
                click.echo(click.style("Commit aborted.", fg="red"))
                break
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
