
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.integrations.researcher import research_jobs

app = FastAPI(title="CareerPilot AI")


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
