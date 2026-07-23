from typing import Iterable, Optional

import click


def prompt_large_diff_mode() -> bool:
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
    return mode.lower() == "s"


def display_generation_result(
    content: str,
    token_usage: Optional[int],
    elapsed_time: float,
    suggest_split: Optional[bool],
    split_reason: Optional[str],
    split_groups: Iterable[str],
    *,
    regenerated: bool = False,
) -> None:
    label = "Regenerated commit message" if regenerated else "Commit message"
    click.echo(click.style(f"{label}: {content}", fg="green"))
    click.echo(click.style(f"Tokens used: {token_usage}", fg="blue"))
    click.echo(click.style(f"Elapsed time: {elapsed_time:.2f} seconds", fg="yellow"))

    if not suggest_split:
        return

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


def show_validation_warning(errors: Iterable[str]) -> None:
    click.echo()
    click.echo(
        click.style(
            "Warning: generated commit message is not compliant with current commit specification.",
            fg="yellow",
        )
    )
    for error in errors:
        click.echo(click.style(f"- {error}", fg="red"))


def prompt_action(*, strict_invalid: bool) -> str:
    available_actions = ["e", "r", "a"] if strict_invalid else ["c", "e", "r", "a"]
    action_prompt = (
        "Action ([e]dit / [r]egenerate / [a]bort)"
        if strict_invalid
        else "Action ([c]ommit / [e]dit / [r]egenerate / [a]bort)"
    )
    return click.prompt(
        action_prompt,
        default="e" if strict_invalid else "c",
        show_default=True,
        type=click.Choice(available_actions, case_sensitive=False),
    )


def edit_message(content: str) -> Optional[str]:
    edited = click.edit(content)
    if not edited:
        click.echo("No changes made.")
        return None

    updated = edited.strip()
    click.echo(click.style(f"New commit message: {updated}", fg="green"))
    return updated


def prompt_additional_prompt() -> str:
    return click.prompt(
        "Additional prompt (optional)",
        default="",
        show_default=False,
    ).strip()


def show_commit_success() -> None:
    click.echo(click.style("Commit successful!", fg="green"))


def show_commit_failure() -> None:
    click.echo(
        click.style(
            "Commit failed. Please fix the issues and try again.",
            fg="red",
        )
    )


def show_commit_aborted() -> None:
    click.echo(click.style("Commit aborted.", fg="red"))
