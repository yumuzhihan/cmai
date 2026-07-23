import pytest
import time

from cmai.core.normalizer import FileDiffSummary, Normalizer
from cmai.providers.base import AIResponse
from cmai.utils.git_staged_analyzer import StagedFileChange


class FlakyRateLimitProvider:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    async def normalize_commit(self, prompt: str, **kwargs) -> AIResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(
                "Error code: 403 - RPM limit exceeded. Please complete identity verification to lift the restriction."
            )
        return AIResponse(
            content="ok",
            model="test",
            provider="test",
            tokens_used=1,
        )


@pytest.mark.anyio
async def test_call_provider_with_retry_on_rate_limit(monkeypatch):
    normalizer = Normalizer()
    provider = FlakyRateLimitProvider(fail_times=2)

    monkeypatch.setattr("cmai.core.normalizer.settings.RETRY_MAX_ATTEMPTS", 3)
    monkeypatch.setattr("cmai.core.normalizer.settings.RETRY_BASE_DELAY_SECONDS", 0.01)
    monkeypatch.setattr("cmai.core.normalizer.settings.RETRY_MAX_DELAY_SECONDS", 0.02)

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr("cmai.core.normalizer.asyncio.sleep", fake_sleep)

    result = await normalizer._call_provider_with_retry(provider, "test")

    assert result.content == "ok"
    assert provider.calls == 3
    assert len(sleep_calls) == 2


@pytest.mark.anyio
async def test_call_provider_with_retry_does_not_retry_non_limit_error(monkeypatch):
    normalizer = Normalizer()

    class NonLimitProvider:
        async def normalize_commit(self, prompt: str, **kwargs) -> AIResponse:
            raise RuntimeError("network disconnected")

    monkeypatch.setattr("cmai.core.normalizer.settings.RETRY_MAX_ATTEMPTS", 5)

    with pytest.raises(RuntimeError, match="network disconnected"):
        await normalizer._call_provider_with_retry(NonLimitProvider(), "test")


def test_heuristic_split_ignores_deleted_and_renamed_files():
    normalizer = Normalizer()
    file_summaries = [
        FileDiffSummary(
            path="src/ui/old_a.py",
            status="deleted",
            summary="remove src/ui/old_a.py",
            tags=("ui", "deleted"),
            area="ui",
        ),
        FileDiffSummary(
            path="src/ui/old_b.py",
            status="deleted",
            summary="remove src/ui/old_b.py",
            tags=("ui", "deleted"),
            area="ui",
        ),
        FileDiffSummary(
            path="db/new_a.py",
            status="renamed",
            summary="rename db/old_a.py to db/new_a.py",
            tags=("database", "renamed"),
            area="database",
        ),
        FileDiffSummary(
            path="db/new_b.py",
            status="renamed",
            summary="rename db/old_b.py to db/new_b.py",
            tags=("database", "renamed"),
            area="database",
        ),
    ]

    suggest_split, reason, groups = normalizer._heuristic_split(file_summaries)

    assert suggest_split is False
    assert reason == ""
    assert groups == []


@pytest.mark.anyio
async def test_aggregate_does_not_suggest_split_for_structural_changes():
    normalizer = Normalizer()
    file_summaries = [
        FileDiffSummary(
            path="src/legacy.py",
            status="deleted",
            summary="remove src/legacy.py",
            tags=("core", "deleted"),
            area="core",
        ),
        FileDiffSummary(
            path="docs/new-name.md",
            status="renamed",
            summary="rename docs/old-name.md to docs/new-name.md",
            tags=("docs", "renamed"),
            area="docs",
        ),
    ]

    aggregate, suggest_split, reason, groups = await normalizer._aggregate_with_ai(
        provider=object(),
        file_summaries=file_summaries,
        language="English",
    )

    assert aggregate == "Staged changes mainly touch: core, docs."
    assert suggest_split is False
    assert reason == ""
    assert groups == []


@pytest.mark.anyio
async def test_summarize_files_with_ai_keeps_order_and_uses_progress(monkeypatch):
    normalizer = Normalizer()

    entries = [
        StagedFileChange(
            path="a.py",
            status="modified",
            full_diff="",
            preview_diff="+a",
            is_preview_only=True,
        ),
        StagedFileChange(
            path="b.py",
            status="modified",
            full_diff="",
            preview_diff="+b",
            is_preview_only=True,
        ),
        StagedFileChange(
            path="c.py",
            status="modified",
            full_diff="",
            preview_diff="+c",
            is_preview_only=True,
        ),
    ]

    class DummyProgress:
        def __init__(self, total: int, desc: str, unit: str):
            self.total = total
            self.desc = desc
            self.unit = unit
            self.current = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, value: int):
            self.current += value

    progress: dict[str, DummyProgress] = {}

    def fake_tqdm(*, total: int, desc: str, unit: str):
        bar = DummyProgress(total=total, desc=desc, unit=unit)
        progress["bar"] = bar
        return bar

    monkeypatch.setattr("cmai.core.normalizer.tqdm", fake_tqdm)

    def fake_summarize(index: int, entry: StagedFileChange, language: str):
        del language
        time.sleep((len(entries) - index) * 0.01)
        if entry.path == "b.py":
            return index, normalizer._heuristic_file_summary(entry)
        return (
            index,
            FileDiffSummary(
                path=entry.path,
                status=entry.status,
                summary=f"custom {entry.path}",
                tags=("core", "modified"),
                area="core",
            ),
        )

    monkeypatch.setattr(
        normalizer,
        "_summarize_file_with_ai_in_thread",
        fake_summarize,
    )

    file_summaries = await normalizer._summarize_files_with_ai(
        provider=object(),
        entries=entries,
        language="English",
    )

    assert [item.path for item in file_summaries] == ["a.py", "b.py", "c.py"]
    assert file_summaries[0].summary == "custom a.py"
    assert file_summaries[1].summary == "update b.py"
    assert file_summaries[2].summary == "custom c.py"

    bar = progress["bar"]
    assert bar.total == 3
    assert bar.desc == "Summarizing files"
    assert bar.unit == "file"
    assert bar.current == 3
