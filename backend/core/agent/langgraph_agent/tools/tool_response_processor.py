"""
Tool Response Manager for handling large tool outputs that exceed context windows.
"""

import json
import logging
from typing import Any, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage, ToolMessage

logger = logging.getLogger(__name__)


class ToolResponseManager:
    """管理工具调用响应，防止超出上下文窗口限制"""

    def __init__(
        self,
        max_tool_response_tokens: int = 4000,
        summarization_model: Optional[BaseLanguageModel] = None,
        enable_chunking: bool = False,
        enable_summarization: bool = False,
        enable_truncation: bool = True,
    ):
        self.max_tool_response_tokens = max_tool_response_tokens
        self.summarization_model = summarization_model
        self.enable_chunking = enable_chunking
        self.enable_summarization = enable_summarization
        self.enable_truncation = enable_truncation

    def estimate_tokens(self, text: str) -> int:
        """估算文本的token数量（简单估算：1个token ≈ 4个字符）"""
        return len(text) // 4

    def process_tool_responses(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """处理消息列表中的工具响应"""
        processed_messages: list[BaseMessage] = []

        for message in messages:
            if isinstance(message, ToolMessage):
                processed_message = self._process_single_tool_response(message)
                processed_messages.append(processed_message)
            else:
                processed_messages.append(message)
        logger.info(f"pre_model_hook process_tool_responses processed_messages count: {len(processed_messages)}")
        return processed_messages

    def _process_single_tool_response(self, tool_message: ToolMessage) -> ToolMessage:
        """处理单个工具响应消息"""
        content = tool_message.content

        if not isinstance(content, str):
            return tool_message

        token_count = self.estimate_tokens(content)

        if token_count <= self.max_tool_response_tokens:
            return tool_message

        logger.info(f"Tool response too long ({token_count} tokens), processing...")

        # 尝试不同的处理策略
        processed_content = None

        # 策略1: 智能摘要
        if self.enable_summarization and self.summarization_model:
            try:
                processed_content = self._summarize_content(content, tool_message.name)
                if processed_content and self.estimate_tokens(processed_content) <= self.max_tool_response_tokens:
                    logger.info("Successfully summarized tool response")
                    return ToolMessage(
                        content=f"[SUMMARIZED] {processed_content}",
                        tool_call_id=tool_message.tool_call_id,
                        name=tool_message.name,
                    )
            except Exception as e:
                logger.exception("Summarization failed.")

        # 策略2: 智能分块
        if self.enable_chunking:
            processed_content = self._chunk_content(content, tool_message.name)
            if processed_content:
                logger.info("Successfully chunked tool response")
                return ToolMessage(
                    content=processed_content, tool_call_id=tool_message.tool_call_id, name=tool_message.name
                )

        # 策略3: 智能截断
        if self.enable_truncation:
            processed_content = self._truncate_content(content, tool_message.name)
            logger.info("Truncated tool response")
            return ToolMessage(
                content=processed_content, tool_call_id=tool_message.tool_call_id, name=tool_message.name
            )

        return tool_message

    def _summarize_content(self, content: str, tool_name: Optional[str]) -> Optional[str]:
        """使用LLM对内容进行摘要"""
        if not self.summarization_model:
            return None

        try:
            prompt = f"请简洁地总结以下内容，保留最重要的信息：\n\n{content[:32000]}"

            if tool_name:
                # 根据工具类型定制摘要提示
                if "search" in tool_name.lower():
                    prompt = f"请简洁地总结以下搜索结果的关键信息，保留最重要的内容：\n\n{content[:32000]}"
                elif "file" in tool_name.lower() or "read" in tool_name.lower():
                    prompt = f"请简洁地总结以下文件内容的核心要点：\n\n{content[:32000]}"
                elif "database" in tool_name.lower() or "query" in tool_name.lower():
                    prompt = f"请简洁地总结以下查询结果的关键数据：\n\n{content[:32000]}"

            response = self.summarization_model.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.exception("Summarization error.")
            return None

    def _chunk_content(self, content: str, tool_name: Optional[str]) -> str:
        """智能分块内容，保留最重要的部分"""
        target_length = self.max_tool_response_tokens * 4  # 转换回字符数

        # 如果是JSON数据，尝试保留结构化信息
        if self._is_json_content(content):
            return self._chunk_json_content(content, target_length)

        # 如果是搜索结果，保留前几个结果
        if tool_name and "search" in tool_name.lower():
            return self._chunk_search_results(content, target_length)

        # 如果是代码文件，保留开头和结构信息
        if self._is_code_content(content):
            return self._chunk_code_content(content, target_length)

        # 默认策略：保留开头和结尾
        return self._chunk_text_content(content, target_length)

    def _is_json_content(self, content: str) -> bool:
        """检查内容是否为JSON格式"""
        try:
            json.loads(content.strip())
            return True
        except:
            return False

    def _is_code_content(self, content: str) -> bool:
        """检查内容是否为代码"""
        code_indicators = [
            "def ",
            "class ",
            "import ",
            "function",
            "var ",
            "const ",
            "public class",
            "private ",
            "protected ",
            "#!/",
        ]
        return any(indicator in content[:1000] for indicator in code_indicators)

    def _is_search_results(self, content: str) -> bool:
        """检查内容是否为搜索结果"""
        search_indicators = ["search results", "found", "matches", "result"]
        return any(indicator in content.lower()[:200] for indicator in search_indicators)

    def _chunk_json_content(self, content: str, target_length: int) -> str:
        """分块JSON内容"""
        try:
            data = json.loads(content)

            if isinstance(data, list):
                # 如果是列表，只保留前几个元素
                chunk_size = max(1, len(data) // 4)
                chunked_data = data[:chunk_size]
                result = json.dumps(chunked_data, indent=2, ensure_ascii=False)
                return f"[CHUNKED - Showing {len(chunked_data)}/{len(data)} items]\n{result}"

            elif isinstance(data, dict):
                # 如果是字典，保留主要键值对
                important_keys = list(data.keys())[:10]  # 只保留前10个键
                chunked_dict = {k: data[k] for k in important_keys if k in data}
                result = json.dumps(chunked_dict, indent=2, ensure_ascii=False)
                return f"[CHUNKED - Showing {len(important_keys)}/{len(data)} keys]\n{result}"

        except Exception as e:
            logger.exception("JSON chunking failed.")
            return self._chunk_text_content(content, target_length)

        return content[:target_length] + "\n[CONTENT TRUNCATED]"

    def _chunk_search_results(self, content: str, target_length: int) -> str:
        """分块搜索结果"""
        # 尝试按行分割，保留前几个结果
        lines = content.split("\n")
        result_lines = []
        current_length = 0

        for line in lines:
            if current_length + len(line) > target_length:
                break
            result_lines.append(line)
            current_length += len(line)

        result = "\n".join(result_lines)
        if len(content) > len(result):
            result += "\n[SEARCH RESULTS TRUNCATED - Showing partial results]"

        return result

    def _chunk_code_content(self, content: str, target_length: int) -> str:
        """分块代码内容"""
        lines = content.split("\n")

        # 保留文件开头的重要信息（导入、类定义等）
        important_lines = []
        regular_lines = []

        for line in lines:
            stripped = line.strip()
            if (
                stripped.startswith(
                    (
                        "import ",
                        "from ",
                        "class ",
                        "def ",
                        "function",
                        "var ",
                        "const ",
                        "#!/",
                        "# -*- coding:",
                        '"""',
                        "'''",
                    )
                )
                or stripped.startswith("#")
                and len(stripped) > 20
            ):  # 长注释
                important_lines.append(line)
            else:
                regular_lines.append(line)

        # 组合结果
        result_lines = important_lines
        current_length = sum(len(line) for line in result_lines)

        # 添加部分常规内容
        for line in regular_lines:
            if current_length + len(line) > target_length:
                break
            result_lines.append(line)
            current_length += len(line)

        result = "\n".join(result_lines)
        if len(content) > len(result):
            result += "\n# [CODE CONTENT TRUNCATED]"

        return result

    def _chunk_text_content(self, content: str, target_length: int) -> str:
        """分块普通文本内容"""
        if len(content) <= target_length:
            return content

        # 保留开头和结尾
        head_length = target_length // 2
        tail_length = target_length - head_length - 100  # 为省略符号留空间

        head = content[:head_length]
        tail = content[-tail_length:] if tail_length > 0 else ""

        return f"{head}\n\n[... CONTENT TRUNCATED ({len(content)} chars total) ...]\n\n{tail}"

    def _truncate_content(self, content: str, tool_name: Optional[str]) -> str:
        """简单截断内容"""
        target_length = self.max_tool_response_tokens * 4

        if len(content) <= target_length:
            return content

        truncated = content[:target_length]
        return f"{truncated}\n\n[CONTENT TRUNCATED - Original length: {len(content)} chars]"


from langgraph.utils.runnable import RunnableCallable


def create_tool_response_hook(
    max_tool_response_tokens: int = 5000, summarization_model: Optional[BaseLanguageModel] = None, **kwargs
) -> RunnableCallable:
    """创建用于pre_model_hook的工具响应处理函数"""

    manager = ToolResponseManager(
        max_tool_response_tokens=max_tool_response_tokens, summarization_model=summarization_model, **kwargs
    )

    async def tool_response_hook(state: dict[str, Any]) -> dict[str, Any]:
        """处理工具响应的异步hook函数"""
        messages = state.get("messages", [])

        # 处理工具响应，生成新的消息列表用于LLM输入
        processed_messages = manager.process_tool_responses(messages)

        logger.info(f"tool_response_hook processed_messages count: {len(processed_messages)}")

        # 返回llm_input_messages，这样不会修改状态中的messages
        # 但会将处理后的消息作为LLM的输入
        return {"llm_input_messages": processed_messages}

    return RunnableCallable(
        None,  # 不提供同步版本
        tool_response_hook,  # 异步版本
        name="tool_response_hook",
    )
