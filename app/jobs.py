import time
import uuid
jobs = {}
def create_job():
    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"id": job_id, "status": "queued", "created_at": time.time(),
                    "result": None, "error": None}
    return job_id
def run_job(job_id, func, *args):
    jobs[job_id]["status"] = "running"
    try:
        jobs[job_id]["result"] = func(*args)
        jobs[job_id]["status"] = "done"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)[:300]