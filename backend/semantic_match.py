"""B5: Semantic search with pre-built embeddings."""
import os, numpy as np
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from sentence_transformers import SentenceTransformer

_EMBEDDINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "embeddings.npz")
_model = None
_embeddings = None
_ids = None


def _load():
    global _model, _embeddings, _ids
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        data = np.load(_EMBEDDINGS_PATH)
        _embeddings = data["embeddings"]
        _ids = data["ids"]
    return _model, _embeddings, _ids


def semantic_topk(resume_text: str, k: int = 60) -> list:
    """Return source::external_id for top-k jobs matching the resume."""
    model, embs, ids = _load()
    rvec = model.encode([resume_text], normalize_embeddings=True)[0]
    sims = embs @ rvec
    top_idx = np.argsort(-sims)[:k]
    return [ids[i] for i in top_idx]


def semantic_topk_with_scores(resume_text: str, k: int = 60):
    """Return [(source::external_id, cos_score), ...] sorted by score desc."""
    model, embs, ids = _load()
    rvec = model.encode([resume_text], normalize_embeddings=True)[0]
    sims = embs @ rvec
    top_idx = np.argsort(-sims)[:k]
    return [(ids[i], float(sims[i])) for i in top_idx]
