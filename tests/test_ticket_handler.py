import json
import unittest
from types import SimpleNamespace

from agents.ticket_handler import TicketHandlerAgent, TicketStore


class FakeLLM:
    def __init__(self, ticket_info):
        self.ticket_info = ticket_info

    async def ainvoke(self, messages):
        return SimpleNamespace(content=json.dumps(self.ticket_info))


class TicketHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_without_id_does_not_create_ticket(self):
        store = TicketStore()
        agent = TicketHandlerAgent(FakeLLM({"action": "query"}), store)

        result = await agent.process({"messages": [SimpleNamespace(content="查询工单进度")], "user_id": "u1"})

        self.assertIn("请提供完整的工单号", result["sub_results"]["ticket_handler"])
        self.assertEqual(store.query_by_user("u1"), [])

    async def test_query_existing_ticket(self):
        store = TicketStore()
        ticket = store.create("general", "medium", "测试", "描述", "u1")
        agent = TicketHandlerAgent(FakeLLM({"action": "query", "ticket_id": ticket["ticket_id"]}), store)

        result = await agent.process({"messages": [SimpleNamespace(content="查询工单")], "user_id": "u1"})

        self.assertIn(ticket["ticket_id"], result["sub_results"]["ticket_handler"])
        self.assertEqual(len(store.query_by_user("u1")), 1)


if __name__ == "__main__":
    unittest.main()
