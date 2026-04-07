"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import logging
import re
import time
from typing import Optional, Dict, Any, List

import httpx
from openai import OpenAI
from openai import APIConnectionError, APITimeoutError

from ..config import Config

logger = logging.getLogger(__name__)

# 网络瞬断重试配置
_RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, httpx.ConnectError, httpx.RemoteProtocolError)
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # 首次重试等待秒数，后续翻倍


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Config.LLM_TIMEOUT,
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数（默认使用配置中的 LLM_MAX_TOKENS）
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        # 如果未指定 max_tokens，使用配置中的默认值
        effective_max_tokens = max_tokens if max_tokens is not None else Config.LLM_MAX_TOKENS

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return content
            except _RETRYABLE_EXCEPTIONS as e:
                last_error = e
                wait = _RETRY_DELAY * (2 ** attempt)
                logger.warning(f"LLM 连接失败（第 {attempt + 1}/{_MAX_RETRIES} 次），{wait}s 后重试: {e}")
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(wait)

        raise last_error
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数（默认使用配置中的 LLM_MAX_TOKENS）

        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")

