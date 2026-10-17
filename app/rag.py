import hashlib
import re
import time
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
    try:
        return llm.extract_graph(chunk)
    except Exception:
        time.sleep(3)
        return llm.extract_graph(chunk)

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
    return {
        "chunks": len(chunks),
        "entities": total_entities,
        "relations": total_relations,
        "failed_chunks": len(errors),
        "errors": errors[:3],
    }

def ask(question):
    found = vectorstore.search_chunks(question, settings.top_k)
    chunks = [c for c in found if c["distance"] <= settings.max_distance]
    if not chunks:
        return {"question": question, "answer": llm.NO_ANSWER, "sources": [], "graph_facts": []}
    facts = graphstore.get_facts([c["id"] for c in chunks], question)
    answer = llm.answer_question(question, chunks, facts)
    return {
        "question": question,
        "answer": answer,
        "sources": [
            {"number": i + 1, "source": c["source"], "score": c["score"], "text": c["text"]}
            for i, c in enumerate(chunks)
        ],
        "graph_facts": facts,
    }