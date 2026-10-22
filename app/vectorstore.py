import chromadb
from sentence_transformers import SentenceTransformer
from .config import settings
client = chromadb.PersistentClient(path=settings.chroma_dir)
collection = client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"}) 
model = SentenceTransformer(settings.embedding_model)
def add_chunks(ids, texts, source):
    embeddings = model.encode(texts).tolist()
    metadatas = [{"source":source} for _ in texts]
    collection.add(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=texts
    )
def search_chunks(query, top_k):
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )
    chunks = []
    for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
    chunk = {
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "distance": round(distance, 4),
            "score": round(1 - distance, 4),
        }
    chunks.append(chunk)
    return chunks
def count_chunks():
    return collection.count()

def list_chunks(limit=100):
    data = collection.get(limit=limit, include=["documents", "metadatas"])
    return [
        {"id": data["ids"][i], "text": data["documents"][i], "source": data["metadatas"][i]["source"]}
        for i in range(len(data["ids"]))
    ]
def get_many(ids):
    if not ids:
        return []
    data = collection.get(ids=ids, include=["documents", "metadatas"])
    by_id = {}
    for i in range(len(data["ids"])):
        by_id[data["ids"][i]] = {
            "id": data["ids"][i],
            "text": data["documents"][i],
            "source": data["metadatas"][i].get("source", ""),
        }
    return [by_id[i] for i in ids if i in by_id]