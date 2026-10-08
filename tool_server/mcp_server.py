"""
MCP工具服务端 — 基于 FastMCP 官方 SDK
通过 @mcp.tool 装饰器定义工具，FastMCP 自动处理：

- input_schema 生成（从类型注解自动推导）

- JSON-RPC 2.0 协议路由

- 工具发现 (tools/list) 与调用 (tools/call)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("FinServe Agent")

# ─── 订单查询 ───

@mcp.tool
async def order_query(order_id: str = "", user_id: str = "") -> dict[str, Any]:
    """查询订单信息，支持按订单号或用户ID查询"""
    return {
        "order_id": order_id or "ORD-20260401-001",
        "status": "shipped",
        "amount": 299.00,
        "product": "智能理财产品A",
        "created_at": "2026-04-01T10:00:00",
    }

# ─── 知识库搜索 ───

@mcp.tool
async def knowledge_search(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """搜索企业知识库，返回相关文档片段"""
    return [
        {"content": f"关于'{query}'的知识库文档片段", "source": "FAQ.md", "score": 0.95},
    ]

# ─── 工单创建 ───

@mcp.tool
async def ticket_create(
    title: str,
    description: str,
    priority: str = "medium",
    category: str = "general",
) -> dict[str, Any]:
    """创建客服工单"""
    return {
        "ticket_id": f"TK-{uuid.uuid4().hex[:8].upper()}",
        "title": title,
        "status": "created",
        "priority": priority,
    }

# ─── 风控检查 ───

@mcp.tool
async def risk_check(user_id: str, action: str, amount: float = 0.0) -> dict[str, Any]:
    """风控接口 — 检查交易/操作的风险等级，金额>5万标记高风险"""
    if amount > 50000:
        risk_level = "high"
    elif amount > 10000:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "user_id": user_id,
        "action": action,
        "amount": amount,
        "risk_level": risk_level,
        "requires_manual_review": risk_level == "high",
    }

# mcp_server.py 末尾追加
if __name__ == "__main__":
    mcp.run(transport="stdio")
