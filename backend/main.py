import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scraper import fetch_posts
from cleaner import clean_posts
from analyzer import analyze_posts
from storage import create_job, set_job_running, save_result, save_error, get_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Reddit Smart Analytics API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    subreddit: str
    sample_size: int = 50


def run_analysis(job_id: str, subreddit: str, sample_size: int) -> None:
    try:
        set_job_running(job_id)
        posts = fetch_posts(subreddit, sample_size)
        cleaned = clean_posts(posts)
        result = analyze_posts(cleaned)
        result["subreddit"] = subreddit
        result["sample_size"] = len(cleaned)
        save_result(job_id, result)
    except Exception as e:
        save_error(job_id, str(e))


@app.post("/analyze")
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    job_id = create_job(req.subreddit, req.sample_size)
    background_tasks.add_task(run_analysis, job_id, req.subreddit, req.sample_size)
    return {"job_id": job_id, "status": "pending"}


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
