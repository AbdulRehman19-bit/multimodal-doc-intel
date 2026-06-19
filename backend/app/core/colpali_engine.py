import os
import pickle
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Optional

import torch
import faiss
from byaldi import RAGMultiModalModel

from app.config import get_settings

settings = get_settings()


class ColPaliEngine:
    """
    ColPali-based visual document retrieval engine.

    How it works:
    1. Each PDF page is rendered as an image (via PDFProcessor)
    2. ColPali encodes each page image into a dense embedding vector
       — it reads tables, charts, handwriting visually, no OCR needed
    3. Embeddings are stored in a FAISS index (per document)
    4. At query time, the question is also embedded and nearest-neighbor
       search returns the top-k most relevant page images
    5. Those page images go to Gemini for visual question answering

    This is the key architectural difference vs standard RAG:
    standard RAG: PDF → extract text → chunk → embed text → retrieve text
    ColPali RAG:  PDF → render pages → embed images → retrieve images → VQA
    """

    def __init__(self):
        self.model: Optional[RAGMultiModalModel] = None
        self._index_cache: dict[str, faiss.Index] = {}
        self._page_map_cache: dict[str, list[int]] = {}
        os.makedirs(settings.index_storage_path, exist_ok=True)

    def _load_model(self):
        """Lazy-load ColPali — heavy model, load once and keep in memory."""
        if self.model is None:
            print(f"Loading ColPali model: {settings.colpali_model_name}")
            self.model = RAGMultiModalModel.from_pretrained(
                settings.colpali_model_name
            )
            print("ColPali model loaded.")

    def build_index(
        self,
        document_id: str,
        page_images: list[Image.Image],
    ) -> str:
        """
        Build a FAISS index from a list of page images for one document.
        Returns the path where the index is saved.
        """
        self._load_model()

        # Encode all pages into embeddings
        # ColPali returns shape (num_pages, embedding_dim)
        embeddings = self._encode_images(page_images)

        # Build a flat L2 FAISS index
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings.astype(np.float32))

        # Page map: index position → page number (1-based)
        page_map = list(range(1, len(page_images) + 1))

        # Persist to disk
        index_path = self._get_index_path(document_id)
        faiss.write_index(index, str(index_path))

        map_path = self._get_map_path(document_id)
        with open(map_path, "wb") as f:
            pickle.dump(page_map, f)

        # Cache in memory for fast subsequent queries
        self._index_cache[document_id] = index
        self._page_map_cache[document_id] = page_map

        return str(index_path)

    def query_index(
        self,
        document_id: str,
        question: str,
        top_k: int = 3,
    ) -> list[tuple[int, float]]:
        """
        Retrieve the top-k most relevant pages for a question.
        Returns list of (page_number, score) tuples.
        """
        self._load_model()

        index = self._load_index(document_id)
        page_map = self._load_page_map(document_id)

        # Encode the question as a query embedding
        query_embedding = self._encode_query(question)

        # Search FAISS
        k = min(top_k, index.ntotal)
        distances, indices = index.search(
            query_embedding.astype(np.float32), k
        )

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            page_number = page_map[idx]
            # Convert L2 distance to a 0-1 relevance score
            score = float(1 / (1 + dist))
            results.append((page_number, score))

        return results

    def _encode_images(self, images: list[Image.Image]) -> np.ndarray:
        """Encode a list of PIL images using ColPali's image encoder."""
        embeddings = []
        for image in images:
            # byaldi handles tokenization and forward pass internally
            emb = self.model.encode_image(image)
            if isinstance(emb, torch.Tensor):
                emb = emb.cpu().detach().numpy()
            # Flatten if ColPali returns per-patch embeddings (mean pool)
            if emb.ndim > 1:
                emb = emb.mean(axis=0)
            embeddings.append(emb)
        return np.array(embeddings)

    def _encode_query(self, question: str) -> np.ndarray:
        """Encode a text query into the same embedding space as images."""
        emb = self.model.encode_query(question)
        if isinstance(emb, torch.Tensor):
            emb = emb.cpu().detach().numpy()
        if emb.ndim > 1:
            emb = emb.mean(axis=0)
        return np.array([emb])

    def _load_index(self, document_id: str) -> faiss.Index:
        if document_id not in self._index_cache:
            index_path = self._get_index_path(document_id)
            if not index_path.exists():
                raise FileNotFoundError(
                    f"No index found for document {document_id}. "
                    "Process the document first."
                )
            self._index_cache[document_id] = faiss.read_index(str(index_path))
        return self._index_cache[document_id]

    def _load_page_map(self, document_id: str) -> list[int]:
        if document_id not in self._page_map_cache:
            map_path = self._get_map_path(document_id)
            with open(map_path, "rb") as f:
                self._page_map_cache[document_id] = pickle.load(f)
        return self._page_map_cache[document_id]

    def _get_index_path(self, document_id: str) -> Path:
        return Path(settings.index_storage_path) / f"{document_id}.index"

    def _get_map_path(self, document_id: str) -> Path:
        return Path(settings.index_storage_path) / f"{document_id}.map"

    def index_exists(self, document_id: str) -> bool:
        return self._get_index_path(document_id).exists()


colpali_engine = ColPaliEngine()