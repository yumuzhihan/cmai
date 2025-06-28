from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class AIResponse(BaseModel):
    """
    Base class for AI response models.
    """

    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None


class BaseAIClient(ABC):
    """AI客户端抽象基类"""

    def __init__(
        self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs
    ) -> None:
        """
        初始化AI客户端

        Args:
            api_key (Optional[str], optional): API密钥，不传入则尝试从环境变量获取.
            Defaults to None.
            model (Optional[str], optional): 使用的模型名称，不传入则使用默认模型.
            Defaults to None.
            **kwargs: 其他可选参数，具体取决于子类实现.
        """
        self.api_key = api_key
        self.model = model
        self.kwargs = kwargs

    @abstractmethod
    async def normalize_commit(self, prompt: str, **kargs) -> AIResponse:
        """
        规范化commit消息的抽象方法

        Args:
            prompt (str): 用户输入的提示信息，通常包含待规范化的commit消息和相关上下文信息.

        Returns:
            AIResponse: 包含规范化commit消息的响应对象.
        """
        raise NotImplementedError(
            "Subclasses must implement the normalize_commit method."
        )

    @abstractmethod
    def validate_config(self) -> bool:
        """
        验证配置是否正确，**不会检测API密钥的有效性。**

        如果API密钥无效，会在实际使用中抛出异常。

        Returns:
            bool: 如果配置正确返回True，否则返回False.
        """
        raise NotImplementedError(
            "Subclasses must implement the validate_config method."
        )
