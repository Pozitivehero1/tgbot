"""DuplicateDetector — cosine similarity-based deduplication without external ML libs."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional

from football_bot.repositories.news_repository import NewsRepository
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if len(w) > 2]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {term: (count / total) * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _simple_vector(text: str) -> list[float]:
    """Convert text to a simple normalised bag-of-words vector for SQLite storage."""
    tokens = _tokenize(text)
    counts = Counter(tokens)
    vocab = sorted(counts.keys())
    total = len(tokens) or 1
    return [counts[w] / total for w in vocab]


class DuplicateDetector:
    """Detects near-duplicate articles using TF-IDF cosine similarity."""

    def __init__(
        self,
        repository: NewsRepository,
        threshold: float = 0.85,
    ) -> None:
        self._repo = repository
        self._threshold = threshold
        self._corpus_cache: Optional[list[tuple[str, dict[str, float]]]] = None

    async def _build_corpus(self) -> list[tuple[str, dict[str, float]]]:
        """Load all stored vectors and convert them to dicts for cosine comparison."""
        raw_vectors = await self._repo.get_all_vectors()
        corpus: list[tuple[str, dict[str, float]]] = []
        for item_id, vector_list in raw_vectors:
            if vector_list:
                vec_dict = {str(i): v for i, v in enumerate(vector_list)}
                corpus.append((item_id, vec_dict))
        return corpus

    async def check_and_mark(self, item_id: str, title: str, summary: str) -> Optional[str]:
        """Return the ID of the duplicate if found, else None. Marks duplicates in DB."""
        text = title + " " + summary
        tokens = _tokenize(text)
        new_vec_list = _simple_vector(text)
        new_vec = {str(i): v for i, v in enumerate(new_vec_list)}

        await self._repo.update_vector(item_id, new_vec_list)

        if self._corpus_cache is None:
            self._corpus_cache = await self._build_corpus()

        for existing_id, existing_vec in self._corpus_cache:
            if existing_id == item_id:
                continue
            similarity = _cosine_similarity(new_vec, existing_vec)
            if similarity >= self._threshold:
                await self._repo.mark_duplicate(item_id, existing_id)
                logger.info(
                    "duplicate_detected",
                    item_id=item_id,
                    duplicate_of=existing_id,
                    similarity=round(similarity, 3),
                )
                return existing_id

        self._corpus_cache.append((item_id, new_vec))
        return None

    async def run_batch(self, items: list) -> list:
        """Check a list of NewsItems for duplicates; filter out duplicates."""
        self._corpus_cache = await self._build_corpus()
        unique_items = []
        for item in items:
            duplicate_of = await self.check_and_mark(
                item.item_id, item.title, item.summary
            )
            if not duplicate_of:
                unique_items.append(item)
        logger.info("dedup_complete", input=len(items), unique=len(unique_items))
        return unique_items
