from typing import Dict, Type, Optional, Any, Callable
import importlib
from abc import ABC, abstractmethod

from cmai.config.settings import settings
from cmai.core.get_logger import LoggerFactory
from cmai.providers.base import BaseAIClient


class ProviderFactory:
    """AI Provider 工厂类，用于创建和管理不同的 AI 提供商实例"""

    _instance = None
    _providers: Dict[str, Type[BaseAIClient]] = {}
    _default_provider = "openai"

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = LoggerFactory().get_logger("ProviderFactory")
        self._register_default_providers()
        self._initialized = True

    def _register_default_providers(self):
        """注册默认的 Provider"""
        success_registered = False
        try:
            # 注册 OpenAI 兼容的 Provider（默认）
            from cmai.providers.openai_provider import OpenAIProvider

            self.register_provider("openai", OpenAIProvider)
            self.register_provider("bailian", OpenAIProvider)
            self.register_provider("qwen", OpenAIProvider)
            self.register_provider("deepseek", OpenAIProvider)
            self.register_provider("chatgpt", OpenAIProvider)
            self.register_provider("siliconflow", OpenAIProvider)

            self.logger.info("OpenAI compatible providers registered successfully")

            success_registered = True
        except:
            self.logger.debug("Failed to register OpenAI compatible providers")

        try:
            # 注册 Ollama Provider
            from cmai.providers.ollama_provider import OllamaProvider

            self.register_provider("ollama", OllamaProvider)
            self.register_provider("local", OllamaProvider)

            self.logger.info("Ollama providers registered successfully")

            success_registered = True
        except:
            self.logger.warning(f"Failed to register Ollama provider")

        try:
            # 注册 Zai Provider
            from cmai.providers.zai_provider import ZhipuAiProvider

            self.register_provider("zhipu", ZhipuAiProvider)
            self.register_provider("zhipuai", ZhipuAiProvider)
            self.register_provider("zhipu-ai", ZhipuAiProvider)
            self.register_provider("zhipu-api", ZhipuAiProvider)
            self.register_provider("zai", ZhipuAiProvider)

            self.logger.info("Zai providers registered successfully")

            success_registered = True
        except:
            self.logger.debug(f"Failed to register Zai provider")

        if not success_registered:
            self.logger.error(
                "No compatible AI providers were registered. Please check your configuration."
            )

    def register_provider(self, name: str, provider_class: Type[BaseAIClient]):
        """
        注册一个新的 Provider

        Args:
            name: Provider 名称
            provider_class: Provider 类
        """
        if not issubclass(provider_class, BaseAIClient):
            raise ValueError(f"Provider class must inherit from BaseAIClient")

        self._providers[name.lower()] = provider_class
        self.logger.debug(f"Registered provider: {name} -> {provider_class.__name__}")

    def unregister_provider(self, name: str):
        """注销一个 Provider"""
        name = name.lower()
        if name in self._providers:
            del self._providers[name]
            self.logger.debug(f"Unregistered provider: {name}")
        else:
            self.logger.warning(f"Provider {name} not found for unregistration")

    def set_default_provider(self, name: str):
        """设置默认 Provider"""
        if name.lower() in self._providers:
            self._default_provider = name.lower()
            self.logger.info(f"Default provider set to: {name}")
        else:
            raise ValueError(f"Provider {name} is not registered")

    def create_provider(
        self,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> BaseAIClient:
        """
        创建 Provider 实例

        Args:
            provider_name: Provider 名称，如果为空则使用默认或配置中的值
            api_key: API 密钥
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            BaseAIClient: Provider 实例
        """
        # 确定要使用的 provider 名称
        final_provider_name = self._determine_provider_name(provider_name)

        # 获取 Provider 类
        provider_class = self._get_provider_class(final_provider_name)

        # 准备初始化参数
        init_kwargs = self._prepare_init_kwargs(
            final_provider_name, api_key, model, **kwargs
        )

        try:
            # 创建实例
            provider_instance = provider_class(**init_kwargs)

            # 验证配置
            if (
                hasattr(provider_instance, "validate_config")
                and not provider_instance.validate_config()
            ):
                self.logger.warning(
                    f"Provider {final_provider_name} configuration validation failed"
                )

            self.logger.info(
                f"Created provider: {final_provider_name} with model: {init_kwargs.get('model', 'default')}"
            )
            return provider_instance

        except Exception as e:
            self.logger.error(f"Failed to create provider {final_provider_name}: {e}")
            raise

    def _determine_provider_name(self, provider_name: Optional[str]) -> str:
        """确定要使用的 provider 名称"""
        if provider_name:
            return provider_name.lower()

        # 从配置中获取
        if hasattr(settings, "PROVIDER") and settings.PROVIDER:
            return settings.PROVIDER.lower()

        # 使用默认值
        return self._default_provider

    def _get_provider_class(self, provider_name: str) -> Type[BaseAIClient]:
        """获取 Provider 类"""
        provider_name = provider_name.lower()

        if provider_name in self._providers:
            return self._providers[provider_name]

        # 如果没找到，尝试动态加载
        if self._try_dynamic_load(provider_name):
            return self._providers[provider_name]

        # 最后使用默认 provider
        self.logger.warning(
            f"Provider {provider_name} not found, falling back to default: {self._default_provider}"
        )
        if self._default_provider in self._providers:
            return self._providers[self._default_provider]

        raise ValueError(f"No suitable provider found for: {provider_name}")

    def _try_dynamic_load(self, provider_name: str) -> bool:
        """尝试动态加载 Provider"""
        try:
            # 尝试加载模块
            module_name = f"cmai.providers.{provider_name}"
            module = importlib.import_module(module_name)

            # 尝试找到 Provider 类
            class_name = f"{provider_name.title()}Provider"
            if hasattr(module, class_name):
                provider_class = getattr(module, class_name)
                self.register_provider(provider_name, provider_class)
                self.logger.info(f"Dynamically loaded provider: {provider_name}")
                return True

        except ImportError:
            self.logger.debug(f"Failed to dynamically load provider: {provider_name}")

        return False

    def _prepare_init_kwargs(
        self, provider_name: str, api_key: Optional[str], model: Optional[str], **kwargs
    ) -> Dict[str, Any]:
        """准备初始化参数"""
        init_kwargs = kwargs.copy()

        # 设置 API key
        if api_key:
            init_kwargs["api_key"] = api_key
        elif hasattr(settings, "API_KEY") and settings.API_KEY:
            init_kwargs["api_key"] = settings.API_KEY

        # 设置模型
        if model:
            init_kwargs["model"] = model
        elif hasattr(settings, "MODEL") and settings.MODEL:
            init_kwargs["model"] = settings.MODEL

        if init_kwargs.get("model") is None:
            raise ValueError(
                "Model must be specified either as an argument or in settings"
            )

        # 针对特定 provider 的特殊处理
        if provider_name == "ollama":
            # Ollama 特殊配置
            if hasattr(settings, "OLLAMA_HOST") and settings.OLLAMA_HOST:
                init_kwargs["host"] = settings.OLLAMA_HOST
            if not init_kwargs.get("model"):
                init_kwargs["model"] = "qwen3:8b"

        return init_kwargs

    def list_providers(self) -> Dict[str, str]:
        """列出所有已注册的 Provider"""
        return {name: cls.__name__ for name, cls in self._providers.items()}

    def get_provider_info(self, provider_name: str) -> Dict[str, Any]:
        """获取 Provider 信息"""
        provider_name = provider_name.lower()
        if provider_name not in self._providers:
            return {"error": f"Provider {provider_name} not found"}

        provider_class = self._providers[provider_name]
        return {
            "name": provider_name,
            "class": provider_class.__name__,
            "module": provider_class.__module__,
            "doc": provider_class.__doc__ or "No documentation available",
        }


def create_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseAIClient:
    """
    便捷函数：创建 Provider 实例

    Examples:
        # 创建默认 provider (OpenAI 兼容)
        provider = create_provider()

        # 创建 Ollama provider
        provider = create_provider("ollama")

        # 创建指定模型的 provider
        provider = create_provider("qwen", model="qwen-turbo-latest")

        # 创建带 API key 的 provider
        provider = create_provider("openai", api_key="your-api-key")
    """
    factory = ProviderFactory()
    return factory.create_provider(provider_name, api_key, model, **kwargs)


def register_custom_provider(name: str, provider_class: Type[BaseAIClient]):
    """
    便捷函数：注册自定义 Provider

    Example:
        class MyCustomProvider(BaseAIClient):
            # ... 实现

        register_custom_provider("mycustom", MyCustomProvider)
    """
    factory = ProviderFactory()
    factory.register_provider(name, provider_class)


def list_available_providers() -> Dict[str, str]:
    """
    便捷函数：列出所有可用的 Provider

    Returns:
        Dict[str, str]: Provider 名称到类名的映射
    """
    factory = ProviderFactory()
    return factory.list_providers()
