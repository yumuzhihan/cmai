from typing import Optional

import click

from cmai.cli.session import CommitSession


@click.command()
@click.argument("message", type=str, required=True)
@click.option(
    "--config", "-c", help="The path to the configuration file", default=None, type=str
)
@click.option(
    "--repo", "-r", help="The path to the Git repository", default=None, type=str
)
@click.option(
    "--language", "-l", help="The language for the response", default=None, type=str
)
def main(
    message: str,
    config: Optional[str] = None,
    repo: Optional[str] = None,
    language: Optional[str] = None,
) -> None:
    """Normalize informal commit messages"""
    try:
        CommitSession().run(
            message=message,
            config=config,
            repo=repo,
            language=language,
        )
    except Exception as e:
        raise click.ClickException(str(e))
