import subprocess

from click.testing import CliRunner

from cmai.main import main
from cmai.providers.base import AIResponse
from cmai.utils.git_staged_analyzer import StagedFileChange


def _patch_staged_state(monkeypatch, is_truncated: bool = False):
    entries = [
        StagedFileChange(
            path="app.py",
            status="modified",
            full_diff="diff --git a/app.py b/app.py",
            preview_diff="+print('ok')",
            is_preview_only=False,
        )
    ]

    monkeypatch.setattr(
        "cmai.main.GitStagedAnalyzer.get_staged_entries",
        lambda self: entries,
    )
    monkeypatch.setattr(
        "cmai.main.GitStagedAnalyzer.render_prompt_entries",
        lambda self, in_entries: (["ctx"], is_truncated),
    )


def test_strict_mode_hides_commit_option_when_invalid(monkeypatch):
    async def fake_normalize(*args, **kwargs):
        return AIResponse(
            content="invalid message",
            model="test-model",
            provider="test-provider",
            tokens_used=10,
        )

    monkeypatch.setattr("cmai.main.normalize_commit_async", fake_normalize)
    monkeypatch.setattr("cmai.main.settings.COMMIT_STRICT", True)
    _patch_staged_state(monkeypatch, is_truncated=False)

    runner = CliRunner()
    result = runner.invoke(main, ["fix bug"], input="a\n")

    assert result.exit_code == 0
    assert "Action ([e]dit / [r]egenerate / [a]bort)" in result.output
    assert "Action ([c]ommit / [e]dit / [r]egenerate / [a]bort)" not in result.output


def test_regenerate_then_commit_when_message_becomes_valid(monkeypatch):
    responses = [
        AIResponse(
            content="invalid message",
            model="test-model",
            provider="test-provider",
            tokens_used=10,
        ),
        AIResponse(
            content="fix(core): handle nil input",
            model="test-model",
            provider="test-provider",
            tokens_used=12,
        ),
    ]

    async def fake_normalize(*args, **kwargs):
        return responses.pop(0)

    commit_calls = []

    def fake_subprocess_run(cmd, check=True):
        commit_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr("cmai.main.normalize_commit_async", fake_normalize)
    monkeypatch.setattr("cmai.main.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("cmai.main.settings.COMMIT_STRICT", True)
    _patch_staged_state(monkeypatch, is_truncated=False)

    runner = CliRunner()
    result = runner.invoke(main, ["fix bug"], input="r\n\nc\n")

    assert result.exit_code == 0
    assert "Regenerated commit message: fix(core): handle nil input" in result.output
    assert commit_calls == [["git", "commit", "-m", "fix(core): handle nil input"]]


def test_shows_split_suggestion_but_keeps_flow(monkeypatch):
    async def fake_normalize(*args, **kwargs):
        return AIResponse(
            content="fix(core): tune parser guard",
            model="test-model",
            provider="test-provider",
            tokens_used=12,
            suggest_split=True,
            split_reason="Detected independent UI and database changes.",
            split_groups=["ui: web/app.tsx", "database: db/migrations/001.sql"],
        )

    commit_calls = []

    def fake_subprocess_run(cmd, check=True):
        commit_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr("cmai.main.normalize_commit_async", fake_normalize)
    monkeypatch.setattr("cmai.main.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("cmai.main.settings.COMMIT_STRICT", False)
    _patch_staged_state(monkeypatch, is_truncated=False)

    runner = CliRunner()
    result = runner.invoke(main, ["mixed changes"], input="c\n")

    assert result.exit_code == 0
    assert (
        "Suggestion: detected potentially independent staged changes." in result.output
    )
    assert "Detected independent UI and database changes." in result.output
    assert "- ui: web/app.tsx" in result.output
    assert commit_calls == [["git", "commit", "-m", "fix(core): tune parser guard"]]


def test_large_diff_prompts_mode_and_passes_choice(monkeypatch):
    captured_kwargs = []

    async def fake_normalize(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return AIResponse(
            content="fix(core): handle large diff",
            model="test-model",
            provider="test-provider",
            tokens_used=8,
        )

    commit_calls = []

    def fake_subprocess_run(cmd, check=True):
        commit_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr("cmai.main.normalize_commit_async", fake_normalize)
    monkeypatch.setattr("cmai.main.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("cmai.main.settings.COMMIT_STRICT", False)
    _patch_staged_state(monkeypatch, is_truncated=True)

    runner = CliRunner()
    result = runner.invoke(main, ["large changes"], input="f\nc\n")

    assert result.exit_code == 0
    assert "Detected oversized staged diff" in result.output
    assert captured_kwargs[0]["use_file_summary_for_large_diff"] is False
    assert commit_calls == [["git", "commit", "-m", "fix(core): handle large diff"]]
