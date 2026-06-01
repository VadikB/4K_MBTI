from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass(frozen=True)
class Chunk:
    id: int
    text: str
    source: str
    page_start: int
    page_end: int


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float


def load_chunks(path: Path) -> List[Chunk]:
    chunks: List[Chunk] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            payload = json.loads(line)
            chunks.append(Chunk(**payload))
    return chunks


def embed_texts(
    model: SentenceTransformer,
    texts: Sequence[str],
    batch_size: int = 32,
    show_progress_bar: bool = False,
) -> np.ndarray:
    embeddings = model.encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=show_progress_bar,
    )
    return embeddings.astype("float32")


class FaissRagStore:
    def __init__(self, index_dir: Path):
        import faiss

        metadata_path = index_dir / "metadata.json"
        with metadata_path.open("r", encoding="utf-8") as fh:
            self.metadata = json.load(fh)

        self.model = SentenceTransformer(str(self._resolve_local_model_path(self.metadata["embedding_model"])))
        self._faiss = faiss
        self.index = self._faiss.read_index(str(index_dir / "index.faiss"))
        self.chunks = load_chunks(index_dir / "chunks.jsonl")

    def _resolve_local_model_path(self, model_name: str) -> Path | str:
        candidate = Path(str(model_name))
        if candidate.exists():
            return candidate

        cache_root = Path.home() / ".cache" / "huggingface" / "hub"
        model_cache_dir = cache_root / ("models--" + str(model_name).replace("/", "--"))
        refs_main = model_cache_dir / "refs" / "main"
        if refs_main.exists():
            snapshot_id = refs_main.read_text(encoding="utf-8").strip()
            snapshot_dir = model_cache_dir / "snapshots" / snapshot_id
            if snapshot_dir.exists():
                return snapshot_dir
        return model_name

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        query_embedding = embed_texts(self.model, [query], batch_size=1)
        scores, ids = self.index.search(query_embedding, top_k)
        results: List[SearchResult] = []
        for score, chunk_id in zip(scores[0], ids[0]):
            if chunk_id == -1:
                continue
            results.append(SearchResult(chunk=self.chunks[int(chunk_id)], score=float(score)))
        return results
