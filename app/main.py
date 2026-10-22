import uuid
from fastapi.responses import JSONResponse
from pydantic import Field
from .errors import AppError
import logging
import time
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from . import graphstore, jobs, rag, vectorstore
from .cache import cache
from .config import settings
from .ratelimit import rate_limit
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag")
app = FastAPI(title="vector + graph rag")
class IngestBody(BaseModel):
    text: str = Field(min_length=1)
    source: str = "manual"
class QuestionBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)
@app.middleware("http")
async def timing(request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)
    response.headers["X-Process-Time-ms"] = str(ms)
    log.info("%s %s -> %s in %sms", request.method, request.url.path, response.status_code, ms)
    response.headers["X-Request-ID"] = uuid.uuid4().hex[:8]
    return response
@app.get("/")
def home():
    return {"message": "rag api is running"}
@app.post("/ingest", dependencies=[Depends(rate_limit)])
def ingest(body: IngestBody):
    return rag.ingest(body.text, body.source)
@app.post("/ingest/async", dependencies=[Depends(rate_limit)])
def ingest_async(body: IngestBody, background_tasks: BackgroundTasks):
    job_id = jobs.create_job()
    background_tasks.add_task(jobs.run_job, job_id, rag.ingest, body.text, body.source)
    return {"job_id": job_id, "status": "queued"}
@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job
@app.post("/question", dependencies=[Depends(rate_limit)])
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
@app.get("/cache/stats")
def cache_stats():
    return cache.info()
@app.get("/health")
def health():
    report = {"llm_model": settings.llm_model, "cache": cache.info()}
    try:
        report["vector_db"] = {"ok": True, "chunks": vectorstore.count_chunks()}
    except Exception as e:
        report["vector_db"] = {"ok": False, "error": str(e)[:150]}
    try:
        graphstore.driver.verify_connectivity()
        report["graph_db"] = {"ok": True}
    except Exception as e:
        report["graph_db"] = {"ok": False, "error": str(e)[:150]}
    report["ok"] = report["vector_db"]["ok"] and report["graph_db"]["ok"]
    return report
@app.exception_handler(AppError)
async def handle_app_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
from neo4j.exceptions import ServiceUnavailable, SessionExpired
async def handle_db_down(request, exc):
    return JSONResponse(status_code=503, content={"error": "Graph database is not reachable, try again"})
app.add_exception_handler(ServiceUnavailable, handle_db_down)
app.add_exception_handler(SessionExpired, handle_db_down)