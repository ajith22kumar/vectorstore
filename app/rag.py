import uuid
from . import graphstore, vectorstore, llm
from .config import settings
def split_text(text):
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + settings.chunk_size].strip()
        if piece:
            chunks.append(piece)
        start += settings.chunk_size - settings.chunk_overlap
    return chunks
def ingest(text, source):
    chunks = split_text(text)
    ids = [str(uuid.uuid4()) for _ in chunks]
    vectorstore.add_chunks(ids, chunks, source)
    total_entities = 0
    total_relations = 0
    for chunk_id, chunk in zip(ids, chunks):
        graph = llm.extract_graph(chunk)
        graphstore.save_chunk(
            chunk_id,
            source,
            graph["entities"],
            graph["relations"]
        )
        total_entities += len(graph["entities"])
        total_relations += len(graph["relations"])
    return {
        "chunks": len(chunks),
        "entities": total_entities,
        "relations": total_relations
    }
def ask(question):
    chunks = vectorstore.search_chunks(question, settings.top_k)
    facts = []
    for c in chunks:
        facts.extend(graphstore.get_facts(c["id"]))
    answer = llm.answer_question(question, chunks, facts)
    return {"answer": answer, "chunks": chunks, "facts": facts}
