import json
import unittest
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from agents.supervisor import create_supervisor_graph


class FakeLLM:
    async def ainvoke(self, messages):
        prompt = messages[0].content
        if "工单处理Agent" in prompt:
            content = json.dumps({"action": "create", "ticket_type": "general", "priority": "medium", "summary": "测试工单", "details": "测试"})
        elif "金融合规审查Agent" in prompt:
            content = json.dumps({"passed": True, "risk_level": "low", "violations": [], "suggestions": []})
        else:
            content = "ticket_handler"
        return SimpleNamespace(content=content)


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_ticket_flow_reaches_compliance_and_returns_answer(self):
        graph = create_supervisor_graph(llm=FakeLLM(), enable_checkpointing=False)
        state = {
            "messages": [HumanMessage(content="帮我创建工单")],
            "user_id": "u1",
            "session_id": "s1",
            "intent": "",
            "sub_results": {},
            "compliance_passed": True,
            "final_response": "",
            "current_agent": "",
            "retry_count": 0,
        }

        result = await graph.ainvoke(state)

        self.assertEqual(result["intent"], "ticket_handler")
        self.assertTrue(result["compliance_passed"])
        self.assertIn("工单号", result["final_response"])


if __name__ == "__main__":
    unittest.main()
