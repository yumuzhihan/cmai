from typing import Optional
import os

from anthropic import Anthropic

from cmai.config.settings import settings
from cmai.providers.base import BaseAIClient, AIResponse
from cmai.core.get_logger import LoggerFactory


class AnthropicProvider(BaseAIClient):
    """Anthropic Claude 客户端实现"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        初始化 Anthropic 客户端

        Args:
            api_key (str): API密钥，用于认证请求，默认从环境变量中获取。
            model (str, optional): 使用的模型名称，默认为"claude-haiku-4-5-20251001"。
            **kwargs: 其他可选参数，具体取决于不同的API配置。
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.logger = LoggerFactory().get_logger("AnthropicProvider")
        self.stream_logger = LoggerFactory().get_stream_logger("AnthropicProvider")

        self.api_key = api_key or settings.API_KEY or os.getenv("ANTHROPIC_API_KEY")

        # 验证API Key是否存在
        if not self.api_key:
            raise ValueError("API key is required for AnthropicProvider.")

        # 获取 model
        if not model:
            model = settings.MODEL or "claude-3-5-sonnet-20241022"

        self.model = model

        self.client = Anthropic(api_key=self.api_key, **kwargs)

        self.provider = "anthropic" if not settings.PROVIDER else settings.PROVIDER

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

        stream = self.client.messages.create(
            model=self.model or "claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.MAX_TOKEN,
            stream=True,
            thinking=settings.ENABLE_THINKING,
        )

        response = ""
        is_answering = False
        input_tokens = 0
        output_tokens = 0

        # 处理流式响应
        with stream as completion:
            for event in completion:
                # 处理消息开始事件
                if event.type == "message_start":
                    if hasattr(event, "message") and hasattr(event.message, "usage"):
                        input_tokens = event.message.usage.input_tokens
                        self.logger.debug(f"Input tokens: {input_tokens}")

                # 处理内容块增量
                elif event.type == "content_block_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        if not is_answering:
                            self.logger.debug("Starting to answer...")
                            is_answering = True
                        text = event.delta.text
                        self.stream_logger.info(text)
                        response += text

                # 处理消息结束事件
                elif event.type == "message_delta":
                    if hasattr(event, "usage"):
                        output_tokens = event.usage.output_tokens
                        self.logger.debug(f"Output tokens: {output_tokens}")

        total_tokens = input_tokens + output_tokens
        if total_tokens == 0:
            self.logger.warning("No usage information received")

        self.logger.info(f"Final normalized commit message: {response.strip()}")

        return AIResponse(
            content=response.strip(),
            model=self.model or "claude-haiku-4-5-20251001",
            provider=self.provider,
            tokens_used=total_tokens if total_tokens > 0 else None,
        )
