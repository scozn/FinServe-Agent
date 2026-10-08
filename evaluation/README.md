# 智能客服 RAG 检索评测集

`ragas_retrieval_50.jsonl` 的 50 条问题依据 `data/knowledge_base.md` 编写，覆盖知识库的 8 个正文二级章节，其中 2 条需要同时检索两个章节。此评测集针对 Python 实现；它按 `data.knowledge_loader.chunk_markdown()` 的 `##` 分块方式生成金标准。

每行可用于 Ragas `SingleTurnSample`：

- `user_input`：检索问题。
- `reference`：依据所标知识块人工编写的参考答案。
- `reference_contexts`：对应章节的原文内容。
- `reference_context_ids`：知识库块的真实 `id`，由该块原文的 MD5 前 12 位生成。检索后应填入返回文档的 `id`，不能用 `source`，因为所有章节的 `source` 都是 `knowledge_base.md`。

`reference_documents.json` 以块 ID 为键保存原文及章节信息，便于审查。在 `evaluation` 目录运行以下命令，可从知识库重新生成这两个文件：

```powershell
python build_dataset.py --kb ../data/knowledge_base.md
```

在 `evaluation/` 目录中也可以省略 `--kb`。

## Ragas 端到端评测

评测依赖需另行安装：`pip install "ragas>=0.4,<0.5"`。

`run_ragas_retrieval.py` 按实际 Agent 流程执行：BM25 与 DashScope `text-embedding-v4` 向量检索 → RRF 融合 → DashScope `gte-rerank-v2` 重排 → 生成回答。RRF 取前 4 个候选，重排后使用前 3 个知识块。脚本用 Ragas 0.4 的四个指标逐题评分并输出平均值：

- 忠实度 `Faithfulness`：回答中的事实是否有检索上下文支持。
- 答案准确率 `AnswerAccuracy`：回答与参考答案是否一致。
- 上下文召回率 `ContextRecall`：检索内容是否覆盖参考答案的事实。
- 上下文精确率 `ContextPrecision`：检索内容是否相关且排序靠前。

这四项都由评测模型判断，不是文档 ID 的命中率；分数有模型判断误差。每道题会调用向量、重排、回答和评测模型，运行 50 道题可能产生较多 API 费用。该集只有 8 个知识块和 50 条人工问题，不能代表线上真实用户问题分布。`reference` 是根据知识库编写的内容答案；金融回答中的风险提示仍需人工检查。知识库中的个别时间说明（如退款审核）在不同章节有差异，本集避开了这些相互冲突的事实。

运行前在 `仓库根目录的 .env` 中设置 `DASHSCOPE_API_KEY`。回答沿用项目现有的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `MODEL_NAME`。默认使用百炼北京地域的旧域名；若密钥属于其他地域或使用业务空间专属域名，设置 `DASHSCOPE_BASE_URL` 为对应的域名根地址，例如 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com`。不要在 URL 后添加 `/api/v1`。

在仓库根目录运行：

```powershell
python -u evaluation/run_ragas_retrieval.py
```

首次运行可加 `--limit 3`，先检查模型连接和评测输出，再运行完整数据集。

旧 `vector_store/faiss_index` 是随机向量构成的演示索引，新检索器不会加载或覆盖它。知识块原文在进程内生成 DashScope 向量，因此修改知识库后重启进程即可重新建立向量索引。
