import click

from cmai.cli.commands.commit import commit_command
from cmai.cli.commands.config import config_command


class DefaultCommandGroup(click.Group):
    def __init__(self, *args, default_command: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.default_command = default_command

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if self._should_use_default_command(args):
            args.insert(0, self.default_command)
        return super().parse_args(ctx, args)

    def _should_use_default_command(self, args: list[str]) -> bool:
        if not args:
            return False

        for arg in args:
            if arg in {"--help", "-h"}:
                return False
            if arg.startswith("-"):
                continue
            return arg not in self.commands

        return True


@click.group(cls=DefaultCommandGroup, default_command="commit")
def cli() -> None:
    """CMAI command line interface."""
    return


cli.add_command(commit_command, name="commit")
cli.add_command(config_command, name="config")
