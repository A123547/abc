
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.integrations.researcher import research_jobs
from app.api.extraction import router as extraction_router
app = FastAPI(title="CareerPilot AI")
app.include_router(extraction_router)

class ResearchRequest(BaseModel):
    query: str = Field(min_length=3)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/research")
async def create_research(request: ResearchRequest):
    report = await research_jobs(request.query)
    return {
        "query": request.query,
        "report": report,
    }

@app.get("/")
def home():
    return {
        "project": "CareerPilot AI",
        "status": "running",
        "docs": "/docs",
        "version": "0.2.0"
    }