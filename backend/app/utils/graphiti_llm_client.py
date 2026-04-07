"""
通用 OpenAI 协议兼容的 Graphiti LLM 客户端

适用于所有支持 OpenAI 协议的 LLM 服务（DeepSeek、OpenAI、Qwen、MiniMax 等）。

问题根因:
  Graphiti 内置的 OpenAIClient 使用 beta.chat.completions.parse() (仅 OpenAI 支持)。
  OpenAIGenericClient 虽然使用标准 API，但把 Pydantic 模型的完整 JSON Schema
  (含 title/type/description/anyOf 等嵌套结构) 原样序列化到提示词中，
  部分 LLM 会把 schema 结构本身当作属性值返回，导致 Neo4j 报错:
  "Property values can only be of primitive types or arrays thereof"

解决方案:
  继承 OpenAIGenericClient，只重写 generate_response:
  1. 用简洁的字段描述格式替代原始 JSON Schema，避免 LLM 混淆
  2. 对 LLM 响应做 Pydantic 校验，确保值为 Neo4j 支持的原始类型
  底层 _generate_response 完全保留（标准 chat.completions.create + json_object 模式）
"""

import copy
import json
import logging
import typing
from difflib import get_close_matches

import openai
from pydantic import BaseModel

from graphiti_core.llm_client.client import MULTILINGUAL_EXTRACTION_RESPONSES
from graphiti_core.llm_client.config import ModelSize
from graphiti_core.llm_client.errors import RateLimitError, RefusalError
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)


def _resolve_type_hint(field_schema: dict, required: bool) -> str:
    """从 JSON Schema 字段定义中提取人类可读的类型描述"""
    if "type" in field_schema:
        hint = field_schema["type"]
    elif "anyOf" in field_schema:
        non_null = []
        for t in field_schema["anyOf"]:
            ft = t.get("type")
            if ft and ft != "null":
                non_null.append(ft)
            elif "anyOf" in t:
                for inner in t["anyOf"]:
                    ift = inner.get("type")
                    if ift and ift != "null":
                        non_null.append(ift)
        hint = non_null[0] if non_null else "string"
        if not required:
            hint += " or null"
    else:
        hint = "string"
    return hint


def _build_field_prompt(response_model: type[BaseModel], indent: int = 0) -> str:
    """
    将 Pydantic 模型转换为 LLM 友好的字段描述格式，递归展开嵌套模型。

    示例输出:
    {
      "extracted_entities": [  // List of extracted entities
        {
          "name": <string>,  // Name of the extracted entity
          "entity_type_id": <integer>  // ID of the classified entity type
        }
      ]
    }
    """
    schema = response_model.model_json_schema()
    defs = schema.get("$defs", {})
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    pad = "  " * indent
    inner_pad = "  " * (indent + 1)
    lines = [f"{pad}{{"]
    items = list(properties.items())

    for i, (name, field_schema) in enumerate(items):
        desc = field_schema.get("description", "")
        comma = "," if i < len(items) - 1 else ""
        comment = f"  // {desc}" if desc else ""

        # 检查是否为引用其他模型的数组字段
        nested_model = _resolve_nested_model(field_schema, defs)
        if nested_model is not None:
            lines.append(f'{inner_pad}"{name}": [{comment}')
            nested_prompt = _build_nested_prompt(nested_model, indent + 2)
            lines.append(nested_prompt)
            lines.append(f"{inner_pad}]{comma}")
        else:
            hint = _resolve_type_hint(field_schema, name in required_fields)
            lines.append(f'{inner_pad}"{name}": <{hint}>{comma}{comment}')

    lines.append(f"{pad}}}")
    return "\n".join(lines)


def _resolve_nested_model(field_schema: dict, defs: dict) -> dict | None:
    """如果字段是引用其他模型的数组，返回被引用模型的 schema，否则返回 None"""
    if field_schema.get("type") == "array":
        items = field_schema.get("items", {})
        ref = items.get("$ref")
        if ref and defs:
            ref_name = ref.split("/")[-1]
            return defs.get(ref_name)
    return None


def _build_nested_prompt(model_schema: dict, indent: int) -> str:
    """为嵌套模型生成字段描述"""
    properties = model_schema.get("properties", {})
    required_fields = set(model_schema.get("required", []))

    pad = "  " * indent
    inner_pad = "  " * (indent + 1)
    lines = [f"{pad}{{"]
    items = list(properties.items())

    for i, (name, field_schema) in enumerate(items):
        desc = field_schema.get("description", "")
        comma = "," if i < len(items) - 1 else ""
        hint = _resolve_type_hint(field_schema, name in required_fields)
        comment = f"  // {desc}" if desc else ""
        lines.append(f'{inner_pad}"{name}": <{hint}>{comma}{comment}')

    lines.append(f"{pad}}}")
    return "\n".join(lines)


def _remap_field_names(data: dict, response_model: type[BaseModel]) -> dict:
    """尝试将 LLM 返回的错误字段名映射到模型期望的字段名。

    例如 LLM 返回 {"entity_name": "特朗普"} 但模型期望 "name"，
    通过模糊匹配修复。递归处理嵌套列表中的子模型。
    """
    expected_fields = set(response_model.model_fields.keys())
    result_fields = set(data.keys())

    # 已经匹配的字段不需要处理
    missing = expected_fields - result_fields
    extra = result_fields - expected_fields

    remapped = dict(data)

    # 顶层字段名修复
    if missing and extra:
        for expected_name in list(missing):
            match = get_close_matches(expected_name, list(extra), n=1, cutoff=0.4)
            if match:
                remapped[expected_name] = remapped.pop(match[0])
                extra.discard(match[0])
                missing.discard(expected_name)
            else:
                for extra_name in list(extra):
                    if expected_name in extra_name or extra_name in expected_name:
                        remapped[expected_name] = remapped.pop(extra_name)
                        extra.discard(extra_name)
                        missing.discard(expected_name)
                        break

    # 递归处理嵌套列表字段中的子模型
    for field_name, field_info in response_model.model_fields.items():
        if field_name not in remapped:
            continue
        value = remapped[field_name]
        if not isinstance(value, list):
            continue

        # 检查字段类型是否为 list[SomeBaseModel]
        inner_type = _get_list_inner_model(field_info.annotation)
        if inner_type is None:
            continue

        remapped[field_name] = [
            _remap_field_names(item, inner_type) if isinstance(item, dict) else item
            for item in value
        ]

    return remapped


def _get_list_inner_model(annotation) -> type[BaseModel] | None:
    """从 list[SomeModel] 类型注解中提取内部的 BaseModel 子类"""
    origin = typing.get_origin(annotation)
    if origin is not list:
        return None
    args = typing.get_args(annotation)
    if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
        return args[0]
    return None


def _sanitize_for_neo4j(data: dict) -> dict:
    """确保 dict 中所有值为 Neo4j 支持的原始类型（str/int/float/bool/None/list）"""
    sanitized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            # Neo4j 不支持嵌套 Map，转为 JSON 字符串保留信息
            sanitized[k] = json.dumps(v, ensure_ascii=False)
        else:
            sanitized[k] = v
    return sanitized


class CompatibleGraphitiClient(OpenAIGenericClient):
    """
    兼容所有 OpenAI 协议 LLM 的 Graphiti 客户端。

    与父类 OpenAIGenericClient 的唯一区别:
    - generate_response 中用简洁字段描述替代原始 JSON Schema
    - 对 LLM 响应做 Pydantic 校验 + Neo4j 安全过滤

    底层 _generate_response (标准 API + json_object 模式) 完全不变。
    """

    async def generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        if max_tokens is None:
            max_tokens = self.max_tokens

        # 深拷贝避免多次重试时重复追加提示词
        messages = copy.deepcopy(messages)

        if response_model is not None:
            field_prompt = _build_field_prompt(response_model)
            messages[-1].content += (
                "\n\nRespond ONLY with a JSON object. "
                "You MUST use the EXACT field names shown below (do NOT rename them). "
                "Replace each <type> placeholder with the actual value:\n"
                + field_prompt
            )

        # 附加多语言提取说明（与父类保持一致）
        messages[0].content += MULTILINGUAL_EXTRACTION_RESPONSES

        retry_count = 0
        last_error = None

        while retry_count <= self.MAX_RETRIES:
            try:
                # 调用父类的 _generate_response（标准 API + json_object 模式）
                # 注意: response_model 传 None，避免父类再次追加 schema
                result = await self._generate_response(
                    messages, None, max_tokens=max_tokens, model_size=model_size
                )

                # Pydantic 校验，确保字段值类型正确
                if response_model is not None:
                    try:
                        validated = response_model.model_validate(result)
                        return validated.model_dump()
                    except Exception as ve:
                        # 尝试字段名映射修复（LLM 可能把 name 返回为 entity_name 等）
                        logger.warning(f"Pydantic validation failed, attempting field remap: {ve}")
                        remapped = _remap_field_names(result, response_model)
                        try:
                            validated = response_model.model_validate(remapped)
                            return validated.model_dump()
                        except Exception:
                            logger.warning(f"Remap also failed, sanitizing for Neo4j safety")
                            return _sanitize_for_neo4j(remapped)

                return result

            except (RateLimitError, RefusalError):
                raise
            except (
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.InternalServerError,
            ):
                raise
            except Exception as e:
                last_error = e
                if retry_count >= self.MAX_RETRIES:
                    logger.error(f"Max retries ({self.MAX_RETRIES}) exceeded. Last error: {e}")
                    raise
                retry_count += 1
                messages.append(Message(
                    role="user",
                    content=(
                        f"Previous response was invalid: {e.__class__.__name__}: {str(e)[:200]}. "
                        f"Please respond with actual values, not schema definitions or type names."
                    ),
                ))
                logger.warning(
                    f"Retrying after error (attempt {retry_count}/{self.MAX_RETRIES}): {e}"
                )

        raise last_error or Exception("Max retries exceeded with no specific error")
