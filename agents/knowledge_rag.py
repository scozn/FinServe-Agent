"""
知识检索Agent — RAG知识库问答
负责从向量数据库中检索相关文档，结合上下文生成准确回答。
实现RAG流程：BM25与向量检索 → RRF融合 → 重排序 → 生成回答。
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from memory.hybrid_retriever import HybridRetriever
from tracing.otel_config import trace_agent_call


RAG_SYSTEM_PROMPT = """你是一个专业的知识库问答Agent，负责根据检索到的文档回答用户问题。

回答规则：
1. 严格基于检索到的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，明确告知用户并建议转人工
3. 回答要简洁专业，适合客服场景
4. 对于金融产品信息，必须标注"以上信息仅供参考，具体以合同条款为准"
5. 不要在回答中显示文档来源、文件名或引用标记

回答格式：
- 先直接回答用户问题
- 如有必要补充相关信息
- 金融场景需添加风险提示
"""

class KnowledgeRAGAgent:
    """知识检索Agent - 实现完整RAG流程"""

    def __init__(self, llm: ChatOpenAI, retriever: HybridRetriever | None = None):
        self.llm = llm
        self.retriever = retriever or HybridRetriever()

    @trace_agent_call("rag_retrieve")
    async def retrieve_documents(self, query: str, top_k: int = 4) -> list[dict]:
        """BM25 与 DashScope 向量召回，使用 RRF 融合。"""
        return await asyncio.to_thread(self.retriever.search, query, top_k)

    @trace_agent_call("rag_rerank")
    async def rerank_documents(
        self, query: str, documents: list[dict], top_k: int = 3
    ) -> list[dict]:
        """用 DashScope 对 RRF 候选文档重排。"""
        return await asyncio.to_thread(self.retriever.rerank, query, documents, top_k)

    @trace_agent_call("rag_generate")
    async def generate_answer(self, query: str, context_docs: list[dict]) -> str:
        """基于检索文档生成回答"""
        if not context_docs:
            return "抱歉，知识库中暂未找到与您问题相关的信息。建议您联系人工客服获取帮助。"

        context = "\n\n---\n\n".join(
            doc.get("content", "")
            for doc in context_docs
        )

        messages = [
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"用户问题: {query}\n\n"
                f"检索到的参考文档:\n{context}"
            )),
        ]

        response = await self.llm.ainvoke(messages)
        return response.content

    @trace_agent_call("knowledge_rag_process")
    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        完整RAG流程（作为Graph节点）：
        1. BM25 与 DashScope 向量检索，再经 RRF 融合
        2. DashScope 重排序
        3. 生成回答
        """
        messages = state.get("messages", [])
        if not messages:
            return state

        original_query = messages[-1].content

        raw_docs = await self.retrieve_documents(original_query, top_k=4)

        reranked_docs = await self.rerank_documents(original_query, raw_docs, top_k=3)

        answer = await self.generate_answer(original_query, reranked_docs)

        return {
            **state,
            "sub_results": {
                **state.get("sub_results", {}),
                "knowledge_rag": answer,
            },
        }
