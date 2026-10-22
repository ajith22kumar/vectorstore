import hashlib
import re
import time
from .cache import cache, make_key, index_version, bump_index_version
from . import graphstore, vectorstore, llm
from .config import settings
def split_text(text):
    text = re.sub(r"\s+", " ", text).strip()
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    chunks = []
    current = []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > settings.chunk_size:
            chunks.append(" ".join(current))
            current = current[-1:] if len(current[-1]) <= settings.chunk_overlap else []
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks

def make_chunk_id(source, text):
    return hashlib.sha1((source + "|" + text).encode("utf-8")).hexdigest()[:16]

def extract_with_retry(chunk):
    key = make_key("graph", settings.llm_model, chunk)
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        graph = llm.extract_graph(chunk)
    except Exception:
        time.sleep(3)
        graph = llm.extract_graph(chunk)
    if graph["entities"] or graph["relations"]:  
        cache.set(key, graph, settings.graph_cache_ttl)
    return graph

def ingest(text, source):
    chunks = split_text(text)
    ids = [make_chunk_id(source, c) for c in chunks]
    vectorstore.add_chunks(ids, chunks, source)
    total_entities = 0
    total_relations = 0
    errors = []
    for chunk_id, chunk in zip(ids, chunks):
        try:
            graph = extract_with_retry(chunk)
            graphstore.save_chunk(chunk_id, source, graph["entities"], graph["relations"])
            total_entities += len(graph["entities"])
            total_relations += len(graph["relations"])
        except Exception as e:
            errors.append(str(e)[:200])
    bump_index_version()
    return {
        "chunks": len(chunks),
        "entities": total_entities,
        "relations": total_relations,
        "failed_chunks": len(errors),
        "errors": errors[:3],
        
    }

def vector_retrieve(question):
    found = vectorstore.search_chunks(question, settings.top_k)
    return [c for c in found if c["distance"] <= settings.max_distance]


def graph_retrieve(question, seeds):
    seed_ids = [c["id"] for c in seeds]
    entity_ids = set(graphstore.entities_of_chunks(seed_ids))
    entity_ids |= set(graphstore.find_entities_in_text(question))
    if not entity_ids:
        return [], []

    facts = graphstore.neighbourhood(sorted(entity_ids), settings.graph_hops)

    expanded = set(entity_ids)
    for f in facts:
        expanded.add(f["source_id"])
        expanded.add(f["target_id"])

    chunk_ids = graphstore.chunks_for_entities(sorted(expanded), settings.graph_chunk_limit)
    return vectorstore.get_many(chunk_ids), facts


def reciprocal_rank_fusion(rankings, k=60):
    merged = {}
    for name, ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            entry = merged.setdefault(
                item["id"], {**item, "score": item.get("score", 0), "fused": 0.0, "found_by": []}
            )
            entry["fused"] += 1 / (k + rank)
            entry["found_by"].append(name)
            entry["score"] = max(entry["score"], item.get("score", 0))
    return sorted(merged.values(), key=lambda c: c["fused"], reverse=True)

def ask(question):
    key = make_key("answer", index_version(), settings.llm_model, question.strip().lower())
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    timings = {}

    t = time.perf_counter()
    vector_hits = vector_retrieve(question)
    timings["vector_ms"] = round((time.perf_counter() - t) * 1000)

    t = time.perf_counter()
    graph_hits, facts = graph_retrieve(question, vector_hits)
    timings["graph_ms"] = round((time.perf_counter() - t) * 1000)

    fused = reciprocal_rank_fusion(
        [("vector", vector_hits), ("graph", graph_hits)], settings.rrf_k
    )[: settings.final_chunks]

    if not fused:
        return {"question": question, "answer": llm.NO_ANSWER, "sources": [],
                "graph_facts": [], "timings": timings, "cached": False}

    t = time.perf_counter()
    answer = llm.answer_question(question, fused, facts)
    timings["llm_ms"] = round((time.perf_counter() - t) * 1000)

    result = {
        "question": question,
        "answer": answer,
        "sources": [
            {"number": i + 1, "id": c["id"], "source": c["source"], "text": c["text"],
             "similarity": c["score"], "found_by": c["found_by"], "fused_score": round(c["fused"], 4)}
            for i, c in enumerate(fused)
        ],
        "graph_facts": [{"source": f["source"], "relation": f["relation"], "target": f["target"]} for f in facts],
        "timings": timings,
    }
    cache.set(key, result, settings.answer_cache_ttl)
    return {**result, "cached": False}