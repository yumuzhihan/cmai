import pytest

from cmai.core.normalizer import Normalizer
from cmai.providers.base import AIResponse


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
