from typing import Optional
from ollama import AsyncClient

from cmai.config.settings import settings
from cmai.core.get_logger import LoggerFactory
from cmai.providers.base import BaseAIClient, AIResponse


class OllamaProvider(BaseAIClient):
    def __init__(
        self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs
    ) -> None:
        super().__init__(api_key, model, **kwargs)

        host = "http://localhost:11434"
        if settings.OLLAMA_HOST:
            host = settings.OLLAMA_HOST

        if not self.model:
            self.model = "qwen3:8b"

        self.client = AsyncClient(host=host)

        self.logger = LoggerFactory().get_logger("OllamaProvider")
        self.stream_logger = LoggerFactory().get_stream_logger("OllamaProviderStream")

    def validate_config(self) -> bool:
        """验证配置是否有效"""
        # Ollama 通常不需要 API key，只需要确保能连接到 host
        return True

    def _extract_reasoning_content(
        self, content: str, accumulated_content: str
    ) -> tuple[str, str, bool, bool]:
        """
        从内容中提取思考部分和答案部分

        Returns:
            tuple: (reasoning_content, answer_content, is_reasoning, is_answering)
        """
        full_content = accumulated_content + content

        # 方法1: 检查是否有 <thinking> 标签
        if "<think>" in full_content and "</think>" in full_content:
            import re

            thinking_pattern = r"<think>(.*?)</think>"
            matches = re.findall(thinking_pattern, full_content, re.DOTALL)
            if matches:
                reasoning = "".join(matches)
                answer = re.sub(
                    thinking_pattern, "", full_content, flags=re.DOTALL
                ).strip()
                return reasoning, answer, True, bool(answer)

        elif "<think>" in full_content:
            # 只有开始标记，可能还在思考阶段
            reasoning = full_content.split("<think>", 1)[-1].strip()
            return reasoning, "", True, False

        # 检查是否有其他思考标记
        thinking_markers = [
            ("**思考过程:**", "**答案:**"),
            ("**Thinking:**", "**Answer:**"),
            ("## 思考", "## 答案"),
            ("## Thinking", "## Answer"),
            ("[思考]", "[答案]"),
            ("[Thinking]", "[Answer]"),
        ]

        for start_marker, end_marker in thinking_markers:
            if start_marker in full_content:
                if end_marker in full_content:
                    parts = full_content.split(end_marker, 1)
                    if len(parts) == 2:
                        reasoning_part = parts[0].split(start_marker, 1)[-1].strip()
                        answer_part = parts[1].strip()
                        return reasoning_part, answer_part, True, True
                else:
                    # 只有开始标记，可能还在思考阶段
                    reasoning_part = full_content.split(start_marker, 1)[-1].strip()
                    return reasoning_part, "", True, False

        return "", content, False, True

    async def normalize_commit(self, prompt: str, **kwargs) -> AIResponse:
        diff_content = kwargs.pop("diff_content", None)
        if diff_content:
            log_prompt = prompt.replace(
                diff_content, f"[Diff content hidden, length: {len(diff_content)}]"
            )
        else:
            log_prompt = prompt
        self.logger.debug(f"Normalizing commit with prompt: {log_prompt}")

        reason = ""
        response = ""
        accumulated_content = ""
        is_answering = False
        is_reasoning = False
        total_tokens = 0

        try:
            # 发起流式聊天请求
            stream = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if "message" in chunk:
                    content = chunk["message"].get("content", "")

                    if content:
                        accumulated_content += content

                        # self.logger.debug(f"Received chunk: {content}")

                        # 提取思考内容和答案内容
                        (
                            reasoning_content,
                            answer_content,
                            chunk_is_reasoning,
                            chunk_is_answering,
                        ) = self._extract_reasoning_content(
                            content, accumulated_content
                        )

                        # self.logger.debug(
                        #     f"Extracted reasoning: {reasoning_content}, "
                        #     f"answer: {answer_content}, "
                        #     f"is_reasoning: {chunk_is_reasoning}, "
                        #     f"is_answering: {chunk_is_answering}"
                        # )

                        # 处理思考内容
                        if reasoning_content and chunk_is_reasoning:
                            if not is_reasoning:
                                self.logger.info(
                                    "Detected reasoning content...\nPlease wait..."
                                )
                                is_reasoning = True
                            # 只输出新的思考内容（避免重复）
                            self.stream_logger.info(content)
                            reason = reasoning_content

                        # 处理答案内容
                        if answer_content and chunk_is_answering:
                            if not is_answering:
                                self.stream_logger.info("\n")
                                self.logger.debug("Starting to answer...")
                                is_answering = True
                            self.stream_logger.info(content)
                            response = answer_content

                        # 如果没有检测到特殊格式，按普通内容处理
                        if not chunk_is_reasoning and not chunk_is_answering:
                            if not is_answering:
                                self.stream_logger.info("\n")
                                self.logger.debug("Starting to answer...")
                                is_answering = True
                                continue
                            self.stream_logger.info(content)
                            response += content

                # 处理完成信息和统计
                if chunk.get("done", False):
                    # 获取使用情况统计
                    if "total_duration" in chunk:
                        self.logger.debug(
                            f"Total duration: {chunk['total_duration']} ns"
                        )

                    if "prompt_eval_count" in chunk and "eval_count" in chunk:
                        total_tokens = chunk.get("prompt_eval_count", 0) + chunk.get(
                            "eval_count", 0
                        )
                        self.logger.debug(f"Received usage info: {total_tokens} tokens")

                    # 记录其他有用的统计信息
                    if "load_duration" in chunk:
                        self.logger.debug(f"Load duration: {chunk['load_duration']} ns")
                    if "prompt_eval_duration" in chunk:
                        self.logger.debug(
                            f"Prompt eval duration: {chunk['prompt_eval_duration']} ns"
                        )
                    if "eval_duration" in chunk:
                        self.logger.debug(f"Eval duration: {chunk['eval_duration']} ns")

        except Exception as e:
            self.logger.error(f"Error during Ollama chat: {str(e)}")
            raise

        if total_tokens == 0:
            self.logger.warning("No token usage information received")

        # 最终处理：如果有累积内容但没有正确分离，再次尝试提取
        if accumulated_content and not response:
            _, final_answer, _, _ = self._extract_reasoning_content(
                "", accumulated_content
            )
            if final_answer:
                response = final_answer
            else:
                response = accumulated_content

        final_response = response.strip()
        self.logger.info(f"Final normalized commit message: {final_response}")

        # 如果有思考内容，也记录下来
        if reason.strip():
            self.logger.debug(f"Reasoning process: {reason.strip()}")

        return AIResponse(
            content=final_response,
            model=self.model,
            provider="ollama",
            tokens_used=total_tokens,
        )
