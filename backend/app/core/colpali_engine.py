import os
import pickle
import contextlib
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Optional

# Force CPU before importing anything torch-related
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch
import faiss

from app.config import get_settings

settings = get_settings()


class ColPaliEngine:
    """
    ColPali-based visual document retrieval engine — CPU optimized.

    Key CPU optimizations:
    1. Cast model to float32 after load (bfloat16 has no CPU hardware acceleration)
    2. Patch _attn_implementation to 'eager' to avoid SDPA bfloat16 mask conflicts
    3. Resize pages to 448x448 before encoding (ColPali's native resolution)
    4. Cast all non-input_ids tensors to float32
    5. Use torch.inference_mode() (faster than no_grad on CPU)
    6. Print per-page progress so you can see it's working
    """

    def __init__(self):
        self._rag = None
        self._colpali = None
        self._processor = None
        self._device = settings.colpali_device
        self._index_cache: dict[str, faiss.Index] = {}
        self._page_map_cache: dict[str, list[int]] = {}
        os.makedirs(settings.index_storage_path, exist_ok=True)

    def _load_model(self):
        if self._rag is None:
            from byaldi import RAGMultiModalModel
            print(f"Loading ColPali model on device: {self._device}")

            self._rag = RAGMultiModalModel.from_pretrained(
                settings.colpali_model_name,
                device=self._device,
                verbose=0,
            )

            self._colpali = self._rag.model.model
            self._processor = self._rag.model.processor

            if self._device == "cpu":
                # Cast all parameters to float32 — bfloat16 has no CPU hardware acceleration
                self._colpali = self._colpali.float()

                # Patch every submodule to use eager attention instead of SDPA.
                # SDPA internally generates a bfloat16 causal mask regardless of
                # model dtype, causing a dtype mismatch with our float32 queries.
                for module in self._colpali.modules():
                    if hasattr(module, "config") and hasattr(module.config, "_attn_implementation"):
                        module.config._attn_implementation = "eager"

            self._colpali.eval()
            print("ColPali model loaded and ready.")

    def build_index(
        self,
        document_id: str,
        page_images: list[Image.Image],
    ) -> str:
        self._load_model()

        print(f"Building index for {len(page_images)} pages...")
        embeddings = self._encode_images(page_images)
        print(f"All pages encoded. Embedding shape: {embeddings.shape}")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings.astype(np.float32))

        page_map = list(range(1, len(page_images) + 1))

        index_path = self._get_index_path(document_id)
        faiss.write_index(index, str(index_path))

        map_path = self._get_map_path(document_id)
        with open(map_path, "wb") as f:
            pickle.dump(page_map, f)

        self._index_cache[document_id] = index
        self._page_map_cache[document_id] = page_map

        print(f"Index saved to {index_path}")
        return str(index_path)

    def query_index(
        self,
        document_id: str,
        question: str,
        top_k: int = 3,
    ) -> list[tuple[int, float]]:
        self._load_model()

        index = self._load_index(document_id)
        page_map = self._load_page_map(document_id)

        query_embedding = self._encode_query(question)

        k = min(top_k, index.ntotal)
        distances, indices = index.search(
            query_embedding.astype(np.float32), k
        )

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            page_number = page_map[idx]
            score = float(1 / (1 + dist))
            results.append((page_number, score))

        return results

    def _encode_images(self, images: list[Image.Image]) -> np.ndarray:
        embeddings = []

        for i, image in enumerate(images):
            print(f"  Encoding page {i + 1}/{len(images)}...")

            image = image.resize((448, 448), Image.LANCZOS)
            batch = self._processor.process_images([image])

            # Cast everything to float32 except input_ids (must stay integer).
            # attention_mask comes out as bfloat16 from the processor and must
            # match query dtype — exclude only integer token id tensors.
            batch = {
                k: v.to(self._device).to(torch.float32) if k != "input_ids" else v.to(self._device)
                for k, v in batch.items()
            }

            with torch.inference_mode():
                output = self._colpali(**batch)

            if isinstance(output, torch.Tensor):
                emb = output
            elif hasattr(output, "last_hidden_state"):
                emb = output.last_hidden_state
            else:
                emb = output[0]

            emb = emb.mean(dim=1).squeeze(0).float().cpu().numpy()
            embeddings.append(emb)
            print(f"  Page {i + 1} done. Embedding dim: {emb.shape[0]}")

        return np.array(embeddings)

    def _encode_query(self, question: str) -> np.ndarray:
        batch = self._processor.process_queries([question])

        batch = {
            k: v.to(self._device).to(torch.float32) if k != "input_ids" else v.to(self._device)
            for k, v in batch.items()
        }

        with torch.inference_mode():
            output = self._colpali(**batch)

        if isinstance(output, torch.Tensor):
            emb = output
        elif hasattr(output, "last_hidden_state"):
            emb = output.last_hidden_state
        else:
            emb = output[0]

        emb = emb.mean(dim=1).squeeze(0).float().cpu().numpy()
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