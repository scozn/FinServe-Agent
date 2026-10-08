# FinServe Agent

**面向金融服务场景的多 Agent 智能客服原型。** 基于 FastAPI 与 LangGraph，提供知识库问答、演示工单处理、合规审查和对话页面。

> 当前仓库仅包含 Python 实现。工单、订单和风控工具使用演示数据；项目适合学习与原型验证，不能直接作为真实客服或金融业务系统上线。

## 功能与流程

```text
网页 / REST API
    → Supervisor 路由
    → 知识库问答或工单处理
    → 合规检查
    → 返回答案并记录会话
```

- **知识库问答**：对 `knowledge_base.md` 按章节切分；使用 BM25、DashScope 向量检索、RRF 融合和重排序，再由兼容 OpenAI API 的模型生成回答。
- **工单演示**：根据用户请求创建工单，或用工单号查询进度。工单保存在当前进程内，重启后清空。
- **会话历史**：Redis 可选；未连接时保存在当前进程内。网页的会话列表保存在当前浏览器的 `localStorage`。
- **合规检查**：规则检查敏感词和个人信息，再用模型审查回答。不应将其视为正式的合规保证。
- **工具接口**：FastMCP 提供订单查询、知识库搜索、工单创建和风控检查示例工具；`/api/tools` 可查看和调用它们。这些工具目前没有接入主 Agent 流程或真实业务系统。

## 快速开始

在仓库根目录操作。需要 Python 3.12 和一个兼容 OpenAI Chat Completions 的模型 API Key。使用知识库问答还需要 DashScope API Key；Redis 可选。

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 可用 `Copy-Item .env.example .env` 复制配置文件。编辑 `.env`，至少设置 `OPENAI_API_KEY`；知识库问答还需设置 `DASHSCOPE_API_KEY`。如果使用其他兼容 OpenAI API 的服务，同时修改 `OPENAI_BASE_URL` 和 `MODEL_NAME`。不要把 `.env` 或真实 Key 提交到 GitHub。

从仓库根目录启动：

```bash
python -m api.main
```

打开 [http://localhost:8000/](http://localhost:8000/) 使用聊天页，或打开 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 API 文档。健康检查为 `GET /health`。

### Docker

```bash
docker build -t finserve-agent .
docker run --env-file .env -p 8000:8000 finserve-agent
```

如果使用 Redis，容器内的 `localhost` 指向容器本身，需将 `REDIS_URL` 改为容器可访问的 Redis 地址；未连接时程序使用进程内会话存储。

## API

| 接口 | 说明 |
| --- | --- |
| `POST /api/chat` | 发送消息，返回回答、会话 ID、路由结果和合规状态 |
| `GET /api/history/{session_id}` | 读取会话消息 |
| `GET /api/tools` | 列出演示 MCP 工具 |
| `POST /api/tools/call` | 调用演示工具 |
| `GET /api/metrics` | 查看进程内指标和最近的工具调用 |
| `GET /health` | 健康检查 |

聊天请求示例：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"如何申请退款？"}'
```

再次发送消息时带上返回的 `session_id` 可继续同一会话。网页会自动处理此字段。

在仓库根目录运行本地回归检查：

```bash
python -m unittest discover -s tests -v
```

## 项目结构

```text
FinServe-Agent/
├── agents/          # Supervisor、知识库、工单与合规 Agent
├── api/             # FastAPI 入口
├── data/            # Markdown 知识库与分块逻辑
├── evaluation/      # RAG 检索评测集与脚本
├── frontend/        # 原生 HTML、CSS、JavaScript 页面
├── memory/          # 会话记忆与混合检索
├── tool_server/     # FastMCP 演示工具
├── tracing/         # OpenTelemetry 跟踪
├── .env.example     # 环境变量模板
└── requirements.txt
```

## 评测

`evaluation/` 提供 50 条知识库问答样本和可选的 Ragas 评测脚本。评测会调用外部模型并产生费用；依赖与运行说明见 [评测说明](evaluation/README.md)。

## 当前限制

- 工单和 LangGraph checkpoint 存在进程内；重启或多进程部署后不能保证保留。
- Redis 会话默认保留最近 20 轮，TTL 为 30 分钟；无 Redis 时仅在当前进程内保存。
- 演示接口没有用户认证、权限隔离或真实业务系统连接；不要公开部署到互联网。
- 知识库检索首次使用时需要调用 DashScope 为文档建立内存向量索引；修改知识库后需重启服务。
- 当前聊天 API 返回完整答案，不提供 SSE 流式响应。

## 开源协议

[MIT License](LICENSE)
