"""Evaluate generated RAG answers and retrieved contexts with Ragas."""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from statistics import mean
from types import ModuleType

# Ragas 0.4.3 imports this removed optional integration during initialization.
try:
    import langchain_community.chat_models.vertexai
except ModuleNotFoundError as exc:
    if exc.name != "langchain_community.chat_models.vertexai":
        raise
    vertexai = ModuleType("langchain_community.chat_models.vertexai")
    vertexai.ChatVertexAI = type("ChatVertexAI", (), {})
    sys.modules[vertexai.__name__] = vertexai

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerAccuracy, ContextPrecision, ContextRecall, Faithfulness


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from agents.knowledge_rag import KnowledgeRAGAgent  # noqa: E402
from memory.hybrid_retriever import HybridRetriever  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="用 Ragas 评测 RAG 回答与检索上下文")
    parser.add_argument("--limit", type=int, default=0, help="只评测前 N 条；默认全部 50 条")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit 不能为负数")

    dataset_path = Path(__file__).with_name("ragas_retrieval_50.jsonl")
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    if args.limit:
        rows = rows[:args.limit]
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise RuntimeError("请先在仓库根目录的 .env 中设置 DASHSCOPE_API_KEY")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("请先在仓库根目录的 .env 中设置 OPENAI_API_KEY")

    print("正在初始化知识库向量...", flush=True)
    retriever = HybridRetriever()
    model = os.getenv("MODEL_NAME", "gpt-4o")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    llm = ChatOpenAI(model=model, temperature=0, base_url=base_url)
    agent = KnowledgeRAGAgent(llm, retriever)
    judge_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)
    judge_options = {"extra_body": {"enable_thinking": False}} if model == "deepseek-v4-flash" else {}
    judge_llm = llm_factory(model, client=judge_client, temperature=0, max_tokens=4096, **judge_options)
    metrics = {
        "忠实度": Faithfulness(llm=judge_llm),
        "答案准确率": AnswerAccuracy(llm=judge_llm),
        "上下文召回率": ContextRecall(llm=judge_llm),
        "上下文精确率": ContextPrecision(llm=judge_llm),
    }

    indexed_ids = {doc["id"] for doc in retriever.documents}
    expected_ids = {doc_id for row in rows for doc_id in row["reference_context_ids"]}
    if not expected_ids <= indexed_ids:
        raise RuntimeError("评测集与当前知识库不匹配，请重新生成评测集")

    scores = {name: [] for name in metrics}
    try:
        for number, row in enumerate(rows, start=1):
            question = row["user_input"]
            print(f"[{number}/{len(rows)}] 正在检索、重排并生成回答：{question}", flush=True)
            candidates = await agent.retrieve_documents(question, top_k=4)
            docs = await agent.rerank_documents(question, candidates, top_k=3)
            if not docs:
                raise RuntimeError(f"第 {number} 条未检索到上下文，无法计算 Ragas 指标")
            answer = await agent.generate_answer(question, docs)
            contexts = [doc["content"] for doc in docs]
            reference = row["reference"]

            inputs = {
                "忠实度": dict(user_input=question, response=answer, retrieved_contexts=contexts),
                "答案准确率": dict(user_input=question, response=answer, reference=reference),
                "上下文召回率": dict(user_input=question, retrieved_contexts=contexts, reference=reference),
                "上下文精确率": dict(user_input=question, reference=reference, retrieved_contexts=contexts),
            }
            row_scores = {}
            for name, metric in metrics.items():
                print(f"[{number}/{len(rows)}] 正在评估{name}...", flush=True)
                result = await metric.ascore(**inputs[name])
                if not math.isfinite(result.value):
                    raise RuntimeError(f"第 {number} 条{name}返回无效分数；请检查评测模型的结构化输出")
                row_scores[name] = result.value
                scores[name].append(result.value)
            print(" ".join(f"{name}={value:.3f}" for name, value in row_scores.items()), flush=True)

        print(f"\n样本数: {len(rows)}")
        for name, values in scores.items():
            print(f"平均{name}: {mean(values):.3f}")
    finally:
        await judge_client.close()


if __name__ == "__main__":
    asyncio.run(main())
