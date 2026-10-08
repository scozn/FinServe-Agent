"""BM25 + DashScope embedding retrieval with RRF and DashScope reranking."""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from pathlib import Path

import faiss
import httpx
import numpy as np
from openai import OpenAI

from data.knowledge_loader import chunk_markdown


EMBEDDING_MODEL = "text-embedding-v4"
RERANK_MODEL = "gte-rerank-v2"
DIMENSIONS = 1024
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Use Chinese character bigrams and ASCII terms for BM25."""
    tokens = []
    for part in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower()):
        if "\u4e00" <= part[0] <= "\u9fff":
            tokens.extend(part[i:i + 2] for i in range(len(part) - 1))
            if len(part) == 1:
                tokens.append(part)
        else:
            tokens.append(part)
    return tokens


class HybridRetriever:
    def __init__(self, kb_path: str | Path | None = None):
        kb_path = Path(kb_path) if kb_path else Path(__file__).resolve().parent.parent / "data" / "knowledge_base.md"
        chunks = [chunk for chunk in chunk_markdown(str(kb_path)) if chunk["section"] != "未分类"]
        self.documents = [
            {**chunk, "id": hashlib.md5(chunk["content"].encode()).hexdigest()[:12]}
            for chunk in chunks
        ]
        self.tokenized = [tokenize(doc["content"]) for doc in self.documents]
        self.term_counts = [Counter(tokens) for tokens in self.tokenized]
        self.avg_length = sum(map(len, self.tokenized)) / len(self.tokenized)
        document_frequency = Counter(term for terms in self.term_counts for term in terms)
        self.idf = {
            term: math.log(1 + (len(self.documents) - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }
        self.index = None
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").rstrip("/")
        self._http_client = httpx.Client(trust_env=False, timeout=30)
        self._embedding_client = None

    def _require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("请先设置 DASHSCOPE_API_KEY，再运行混合检索")
        return self.api_key

    def _client(self) -> OpenAI:
        if self._embedding_client is None:
            self._embedding_client = OpenAI(
                api_key=self._require_key(),
                base_url=f"{self.base_url}/compatible-mode/v1",
                http_client=self._http_client,
                max_retries=2,
            )
        return self._embedding_client

    def _embed(self, texts: list[str]) -> np.ndarray:
        response = self._client().embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=DIMENSIONS,
            encoding_format="float",
        )
        vectors = np.asarray(
            [item.embedding for item in sorted(response.data, key=lambda item: item.index)],
            dtype=np.float32,
        )
        if vectors.shape != (len(texts), DIMENSIONS):
            raise RuntimeError("DashScope 返回的向量数量或维度不符合预期")
        faiss.normalize_L2(vectors)
        return vectors

    def _ensure_index(self) -> None:
        if self.index is None:
            vectors = self._embed([doc["content"] for doc in self.documents])
            self.index = faiss.IndexFlatIP(DIMENSIONS)
            self.index.add(vectors)

    def _bm25_scores(self, query: str) -> list[float]:
        scores = []
        query_terms = set(tokenize(query))
        for tokens, counts in zip(self.tokenized, self.term_counts):
            length_norm = 1.5 * (0.25 + 0.75 * len(tokens) / self.avg_length)
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if frequency:
                    score += self.idf[term] * frequency * 2.5 / (frequency + length_norm)
            scores.append(score)
        return scores

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        """Retrieve with BM25 and dense vectors, then merge ranks with RRF."""
        self._ensure_index()
        limit = min(len(self.documents), max(top_k, 20))
        bm25 = self._bm25_scores(query)
        lexical_order = sorted(range(len(bm25)), key=lambda i: bm25[i], reverse=True)
        lexical_order = [i for i in lexical_order if bm25[i] > 0][:limit]
        query_vector = self._embed([query])
        _, vector_indices = self.index.search(query_vector, limit)
        vector_order = [int(i) for i in vector_indices[0] if i >= 0]

        fused = Counter()
        for ranking in (lexical_order, vector_order):
            for rank, index in enumerate(ranking, start=1):
                fused[index] += 1 / (RRF_K + rank)
        order = sorted(fused, key=lambda i: fused[i], reverse=True)[:top_k]
        return [{**self.documents[i], "rrf_score": fused[i]} for i in order]

    def rerank(self, query: str, documents: list[dict], top_k: int = 3) -> list[dict]:
        """Rerank fused candidates using DashScope gte-rerank-v2."""
        if not documents:
            return []
        response = self._http_client.post(
            f"{self.base_url}/api/v1/services/rerank/text-rerank/text-rerank",
            headers={"Authorization": f"Bearer {self._require_key()}"},
            json={
                "model": RERANK_MODEL,
                "input": {"query": query, "documents": [doc["content"] for doc in documents]},
                "parameters": {"top_n": min(top_k, len(documents))},
            },
        )
        response.raise_for_status()
        results = response.json()["output"]["results"]
        return [
            {**documents[result["index"]], "rerank_score": result["relevance_score"]}
            for result in results
        ]
