from fastapi import FastAPI
from pydantic import BaseModel
from . import rag
app = FastAPI(title="vector + graph rag")

class ingestbody(BaseModel):
    text: str
    source: str="manual"
class questionbody(BaseModel):
    question: str

@app.get("/")
def home():
    return{"message": "rag api is running"}
@app.post("/ingest")
def ingest(body: ingestbody):
    return rag.ingest(body.text, body.source)
@app.post("/question")
def question(body: questionbody):
    return rag.ask(body.question)
