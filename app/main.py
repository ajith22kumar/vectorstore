from fastapi import FastAPI
from pydantic import BaseModel
from . import rag, vectorstore, graphstore
app = FastAPI(title="vector + graph rag")
class IngestBody(BaseModel):
    text: str
    source: str = "manual"
class QuestionBody(BaseModel):
    question: str
@app.get("/")
def home():
    return {"message": "rag api is running"}
@app.post("/ingest")
def ingest(body: IngestBody):
    return rag.ingest(body.text, body.source)
@app.post("/question")
def question(body: QuestionBody):
    return rag.ask(body.question)
@app.get("/stats")
def stats():
    return {"chunks_in_vector_db": vectorstore.count_chunks(), "graph": graphstore.get_stats()}
@app.get("/chunks")
def chunks(limit: int = 100):
    return vectorstore.list_chunks(limit)
@app.get("/graph")
def graph(limit: int = 150):
    return graphstore.get_graph(limit)