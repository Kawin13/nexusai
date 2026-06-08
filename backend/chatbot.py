"""
NexusAI — Lightweight FAQ Engine
Replaces sentence-transformers / torch / CUDA with:
  • TF-IDF (scikit-learn) with bigrams
  • Cosine similarity
  • Synonym / abbreviation expansion
  • NLTK lemmatization + stopword removal
  • LRU query cache
"""

import json
import logging
import pickle
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils import preprocess, expand_synonyms, make_doc

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
FAQ_PATH  = BASE_DIR / "data.json"
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── Fallback response when confidence is low ───────────────
FALLBACK_ANSWER = (
    "I couldn't find a precise answer to your question in my knowledge base.\n\n"
    "Try rephrasing, or ask about: AI/ML, Python, Web Development, Cloud Computing, "
    "Databases, DevOps, Cybersecurity, Git, Networking, or Software Engineering."
)


class FAQEngine:
    """
    Fully self-contained FAQ search engine.
    No model downloads, no GPU, no torch — starts in < 3 s.
    """

    def __init__(self):
        self.faqs: list[dict] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None                  # sparse (n_faqs, n_features)
        self._query_cache: dict[str, list] = {}   # simple string → results cache
        self._load_and_index()

    # ─────────────────────── Loading ──────────────────────────

    def _load_and_index(self):
        logger.info("Loading FAQs from data.json …")
        with open(FAQ_PATH, encoding="utf-8") as f:
            self.faqs = json.load(f)
        logger.info(f"Loaded {len(self.faqs)} FAQs")
        self._build_tfidf()

    def _build_tfidf(self):
        """Build (or restore from disk cache) the TF-IDF index."""
        cache_path = CACHE_DIR / "tfidf_v2.pkl"

        # Try cache
        try:
            with open(cache_path, "rb") as f:
                cached = pickle.load(f)
            if cached.get("count") == len(self.faqs):
                self.vectorizer = cached["vectorizer"]
                self.matrix     = cached["matrix"]
                logger.info("TF-IDF index restored from cache")
                return
        except Exception:
            pass

        # Build fresh
        logger.info("Building TF-IDF index …")
        docs = [make_doc(faq) for faq in self.faqs]

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),     # unigrams + bigrams
            max_features=15_000,
            sublinear_tf=True,      # log(1+tf) damping
            min_df=1,
            strip_accents="unicode",
            analyzer="word",
        )
        self.matrix = self.vectorizer.fit_transform(docs)

        # Persist
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(
                    {"count": len(self.faqs), "vectorizer": self.vectorizer, "matrix": self.matrix},
                    f,
                )
            logger.info("TF-IDF index cached to disk")
        except Exception as e:
            logger.warning(f"Could not cache TF-IDF index: {e}")

        logger.info(
            f"TF-IDF ready — {len(self.faqs)} docs × {self.matrix.shape[1]} features"
        )

    # ─────────────────────── Search ───────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return top_k FAQ matches with confidence scores."""
        if not query or not query.strip():
            return []

        # Normalise for cache key
        cache_key = query.strip().lower()[:200]
        if cache_key in self._query_cache:
            return self._query_cache[cache_key][:top_k]

        # Expand and vectorise
        expanded = expand_synonyms(query)
        preprocessed = preprocess(expanded)
        q_vec = self.vectorizer.transform([preprocessed])

        # Raw cosine scores
        scores = cosine_similarity(q_vec, self.matrix).flatten()

        # Rank
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            raw = float(scores[idx])
            if raw < 0.005:
                break
            faq = self.faqs[idx]
            # Scale to 0-100; cap at 99
            confidence = min(99, round(raw * 160))
            results.append({
                "id":         faq["id"],
                "question":   faq["question"],
                "answer":     faq["answer"],
                "topic":      faq["topic"],
                "confidence": confidence,
                "tfidf_score": round(raw, 4),
                # Kept for API compatibility; was "semantic_score" in old engine
                "semantic_score": None,
            })

        # Cache (store full top-20 to serve varying top_k without re-computing)
        self._query_cache[cache_key] = results
        # Prevent unbounded growth
        if len(self._query_cache) > 2000:
            # drop the oldest 500 entries
            for k in list(self._query_cache.keys())[:500]:
                del self._query_cache[k]

        return results[:top_k]

    def get_best_match(self, query: str, confidence_threshold: int = 40) -> dict | None:
        results = self.search(query, top_k=1)
        if results and results[0]["confidence"] >= confidence_threshold:
            return results[0]
        return None

    # ─────────────────────── Helpers ──────────────────────────

    def get_topics(self) -> list[str]:
        return sorted({faq["topic"] for faq in self.faqs})

    def get_faqs_by_topic(self, topic: str) -> list[dict]:
        return [f for f in self.faqs if f["topic"].lower() == topic.lower()]

    def stats(self) -> dict:
        topic_counts: dict[str, int] = {}
        for faq in self.faqs:
            topic_counts[faq["topic"]] = topic_counts.get(faq["topic"], 0) + 1
        return {
            "total_faqs":      len(self.faqs),
            "topics":          topic_counts,
            "tfidf_features":  self.matrix.shape[1] if self.matrix is not None else 0,
            "semantic_enabled": False,   # no sentence-transformers
            "cache_size":      len(self._query_cache),
        }


# ── Singleton ─────────────────────────────────────────────
_engine: FAQEngine | None = None


def get_engine() -> FAQEngine:
    global _engine
    if _engine is None:
        _engine = FAQEngine()
    return _engine
