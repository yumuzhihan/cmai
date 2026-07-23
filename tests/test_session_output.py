from types import SimpleNamespace

import click
from click.testing import CliRunner

from cmai.cli.session import CommitSession
from cmai.providers.base import AIResponse


def test_run_separates_initial_and_regenerated_results(monkeypatch):
    responses = iter(
        [
            AIResponse(
                content="fix(cli): separate streamed output",
                model="test-model",
                provider="test-provider",
                tokens_used=1,
            ),
            AIResponse(
                content="fix(cli): keep output readable",
                model="test-model",
                provider="test-provider",
                tokens_used=2,
            ),
        ]
    )

    monkeypatch.setattr(CommitSession, "_resolve_large_diff_mode", lambda *_: None)
    monkeypatch.setattr(
        CommitSession,
        "_generate_message",
        lambda *_args, **_kwargs: (next(responses), 0.1),
    )
    monkeypatch.setattr(
        CommitSession,
        "_regenerate_message",
        lambda *_args, **_kwargs: (next(responses), 0.1),
    )
    monkeypatch.setattr("cmai.cli.session.resolve_commit_rules", lambda *_: object())
    monkeypatch.setattr(
        "cmai.cli.session.validate_commit_message",
        lambda *_: SimpleNamespace(valid=True, errors=[]),
    )

    actions = iter(["r", "a"])
    monkeypatch.setattr(
        "cmai.cli.session.prompt_action", lambda **_kwargs: next(actions)
    )

    @click.command()
    def command():
        CommitSession().run("separate output")

    result = CliRunner().invoke(command)

    assert result.exit_code == 0
    assert "\nCommit message: fix(cli): separate streamed output" in result.output
    assert (
        "\nRegenerated commit message: fix(cli): keep output readable" in result.output
    )
