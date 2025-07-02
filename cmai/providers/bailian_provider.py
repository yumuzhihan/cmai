from typing import Optional
import os

from openai import OpenAI

from cmai.config.settings import settings
from cmai.providers.base import BaseAIClient, AIResponse
from cmai.core.get_logger import LoggerFactory


class BailianProvider(BaseAIClient):
    """百炼AI客户端实现"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        初始化百炼AI客户端

        Args:
            api_key (str): API密钥，用于认证请求，默认从环境变量中获取。
            model (str, optional): 使用的模型名称，默认为"qwen-turbo-latest"。
            **kwargs: 其他可选参数，具体取决于百炼AI的API配置。
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.logger = LoggerFactory().get_logger("BailianProvider")
        self.stream_logger = LoggerFactory().get_stream_logger("BailianProviderStream")

        # 尝试从环境变量或配置文件中获取API Key
        if not self.api_key:
            env_api_key = os.getenv("DASHSCOPE_API_KEY")
            self.api_key = env_api_key if env_api_key else settings.API_KEY

        # 验证API Key是否存在
        if not self.api_key:
            raise ValueError("API key is required for BailianProvider.")

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

    def validate_config(self) -> bool:
        return bool(self.api_key)

    async def normalize_commit(self, prompt: str, **kargs) -> AIResponse:
        self.logger.debug(f"Normalizing commit with prompt: {prompt}")

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
