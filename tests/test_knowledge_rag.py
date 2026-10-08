import unittest
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from agents.knowledge_rag import KnowledgeRAGAgent


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content="测试回答")


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def search(self, query, top_k):
        self.queries.append(query)
        return [{"content": "测试文档"}]

    def rerank(self, query, documents, top_k):
        self.queries.append(query)
        return documents


class KnowledgeRAGTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_original_question_with_one_model_call(self):
        llm = FakeLLM()
        retriever = FakeRetriever()
        agent = KnowledgeRAGAgent(llm, retriever)

        result = await agent.process({"messages": [HumanMessage(content="有哪些理财产品？")]})

        self.assertEqual(retriever.queries, ["有哪些理财产品？", "有哪些理财产品？"])
        self.assertEqual(llm.calls, 1)
        self.assertEqual(result["sub_results"]["knowledge_rag"], "测试回答")


if __name__ == "__main__":
    unittest.main()
