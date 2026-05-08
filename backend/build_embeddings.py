"""B5: Build embeddings for all jobs with JD text."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sentence_transformers import SentenceTransformer
from backend.db import get_db


def build():
    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    conn = get_db()
    rows = conn.execute(
        "SELECT id, external_id, source, title, jd_raw, company, city FROM jobs WHERE LENGTH(jd_raw) > 100"
    ).fetchall()
    conn.close()

    texts = []
    ids = []
    for r in rows:
        text = f"{r['title']}\n{r['company']}\n{r['city']}\n{r['jd_raw'][:800]}"
        texts.append(text)
        ids.append(f"{r['source']}::{r['external_id']}")

    print(f"Embedding {len(texts)} texts...")
    embs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True)

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    np.savez(os.path.join(out_dir, "embeddings.npz"), ids=np.array(ids), embeddings=embs)
    print(f"Saved {embs.shape} embeddings to data/embeddings.npz")


if __name__ == "__main__":
    build()
