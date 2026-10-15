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
        chunk = {
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"]
        }
        chunks.append(chunk)
    return chunks