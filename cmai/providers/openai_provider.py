from typing import Optional
import os

from openai import OpenAI

from cmai.config.settings import settings
from cmai.providers.base import BaseAIClient, AIResponse
from cmai.core.get_logger import LoggerFactory


class OpenAIProvider(BaseAIClient):
    """OpenAI 兼容客户端实现"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        初始化 openai 兼容类客户端

        Args:
            api_key (str): API密钥，用于认证请求，默认从环境变量中获取。
            model (str, optional): 使用的模型名称，默认为"qwen-turbo-latest"。
            **kwargs: 其他可选参数，具体取决于不同的API配置。
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.logger = LoggerFactory().get_logger("OpenAIProvider")
        self.stream_logger = LoggerFactory().get_stream_logger("OpenAIProvider")

        self.api_key = api_key or settings.API_KEY or os.getenv("CMAI_API_KEY")

        # 验证API Key是否存在
        if not self.api_key:
            raise ValueError("API key is required for OpenAIProvider.")

        # 获取 API Base
        if not settings.API_BASE:
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        else:
            base_url = settings.API_BASE

        # 获取 model
        if not model:
            model = settings.MODEL or "qwen-turbo-latest"

        self.model = model

        self.client = OpenAI(api_key=self.api_key, base_url=base_url, **kwargs)

        self.provider = "unknown" if not settings.PROVIDER else settings.PROVIDER

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
            stream_options={"include_usage": True},
            **kargs,
        )

        reason = ""
        response = ""
        is_answering = False
        is_reasoning = False
        usage = None
        for chunk in completion:
            if chunk.choices:
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

        if usage is None:
            self.logger.warning("No usage information received")
            usage = 0

        self.logger.info(f"Final normalized commit message: {response.strip()}")

        return AIResponse(
            content=response.strip(),
            model=self.model or "qwen-turbo-latest",
            provider="bailian",
            tokens_used=usage,
        )
