import os
from log import logger as log
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """LLM客户端基类，定义统一接口"""
    @abstractmethod
    def invoke(self, prompt: str, images: list = None) -> str:
        """调用LLM服务
        Args:
            prompt: 文本提示
            images: 图像列表，每个元素为{'path': str, 'description': str}
        Returns:
            LLM返回的文本结果
        """
        pass

class OpenAIClient(BaseLLMClient):
    """OpenAI API客户端"""
    def __init__(self, api_key: str = None, model: str = "gpt-4o", base_url: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """初始化OpenAI客户端"""
        try:
            import openai
            openai.api_key = self.api_key
            if self.base_url:
                openai.base_url = self.base_url
            self._client = openai
        except ImportError:
            log.error("未安装openai库，请使用pip install openai安装")
            raise
        except Exception as e:
            log.error(f"OpenAI客户端初始化失败: {str(e)}")
            raise

    def invoke(self, prompt: str, images: list = None) -> str:
        """调用OpenAI API，仅支持文本输入"""
        try:
            # 移除多模态支持，始终使用纯文本输入
            messages = [{
                "role": "user",
                "content": prompt
            }]
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=8192
            )
            return response.choices[0].message.content
        except Exception as e:
            log.error(f"OpenAI API调用失败: {str(e)}")
            raise


class LLMClientFactory:
    """LLM客户端工厂类，用于创建不同类型的LLM客户端"""
    @staticmethod
    def create_client(service_type: str, base_url: str = None, **kwargs) -> BaseLLMClient:
        """创建LLM客户端实例
        Args:
            service_type: 服务类型，支持"openai"、"anthropic"
            base_url: 自定义API基础地址
            **kwargs: 客户端初始化参数
        Returns:
            对应的LLM客户端实例
        """
        if service_type.lower() == "openai":
            return OpenAIClient(base_url=base_url, **kwargs)
        else:
            raise ValueError(f"不支持的LLM服务类型: {service_type}")