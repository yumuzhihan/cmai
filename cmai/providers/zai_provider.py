import os
from zai import ZhipuAiClient
from zai.types.chat import ChatCompletionChunk

from cmai.providers.base import AIResponse

from .base import BaseAIClient
from cmai.config.settings import settings
from cmai.core.get_logger import LoggerFactory


class ZhipuAiProvider(BaseAIClient):
    """智谱 AI 实现"""

    def __init__(
        self, api_key: str | None = None, model: str | None = None, **kwargs
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.logger = LoggerFactory().get_logger("ZhipuAiProvider")
        self.stream_logger = LoggerFactory().get_stream_logger("ZhipuAiProvider")

        self.api_key = api_key or settings.API_KEY or os.getenv("CMAI_API_KEY")

        if not self.api_key:
            raise ValueError("API key is required for ZhipuAiProvider.")

        base_url = settings.API_BASE or os.getenv("ZHIPUAI_BASE_URL") or None

        self.client = ZhipuAiClient(api_key=self.api_key, base_url=base_url, **kwargs)

        self.model = model or settings.MODEL or "glm-4.5-flash"

    def validate_config(self) -> bool:
        return bool(self.api_key)

    async def normalize_commit(self, prompt: str, **kargs) -> AIResponse:
        diff_content = kargs.pop("diff_content", None)
        if diff_content:
            log_prompt = prompt.replace(
                diff_content, f"[Diff content hidden, length: {len(diff_content)}]"
            )
        else:
            log_prompt = prompt
        self.logger.debug(f"Normalizing commit with prompt: {log_prompt}")

        completion = self.client.chat.completions.create(
            model=self.model or "qwen-turbo-latest",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            thinking={"type": "enabled" if settings.ENABLE_THINKING else "disabled"},
            **kargs,
        )

        reason = ""
        response = ""
        is_answering = False
        is_reasoning = False
        usage = None
        for chunk in completion:
            if isinstance(chunk, ChatCompletionChunk):
                if chunk.choices[0]:
                    delta = chunk.choices[0].delta
                    if (
                        hasattr(delta, "reasoning_content")
                        and getattr(delta, "reasoning_content", None) is not None
                    ):
                        if not is_reasoning:
                            self.logger.info(
                                "Detected reasoning content...\nPlease wait..."
                            )
                            is_reasoning = True
                        self.stream_logger.info(getattr(delta, "reasoning_content", ""))
                        reason += getattr(delta, "reasoning_content", "")
                    else:
                        if not is_answering:
                            self.stream_logger.info("\n")
                            self.logger.debug("Starting to answer...")
                            is_answering = True
                        self.stream_logger.info(chunk.choices[0].delta.content or "")
                        response += chunk.choices[0].delta.content or ""
                elif chunk.usage:
                    usage = chunk.usage.total_tokens
                    self.logger.debug(f"Received usage info: {usage} tokens")
                else:
                    self.logger.warning(f"Unexpected chunk received: {chunk}")
            else:
                self.logger.warning(f"Unexpected chunk received: {chunk}")

        if usage is None:
            self.logger.warning("No usage information received")
            usage = 0

        self.logger.info(f"Final normalized commit message: {response.strip()}")

        return AIResponse(
            content=response.strip(),
            model=self.model or "glm-4.5-flash",
            provider="zai",
            tokens_used=usage,
        )
