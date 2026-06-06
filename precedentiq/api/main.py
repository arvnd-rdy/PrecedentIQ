from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from precedentiq.data.database import PrecedentIQDB
from precedentiq.services.ingestion import CaseIngestionService
from precedentiq.services.search_service import PrecedentSearchService

load_dotenv()

DB_PATH = os.getenv("PRECEDENTIQ_DB_PATH", "precedentiq.sqlite")
db = PrecedentIQDB(DB_PATH)
app = FastAPI(title="PrecedentIQ", version="0.1.0")


class SearchRequest(BaseModel):
    case_text: str
    query: str = ""
    top_k: int = 5


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/index/sample")
def index_sample() -> dict[str, int]:
    cases, sections, chunks = CaseIngestionService(db).ingest_sample_corpus()
    return {"cases": len(cases), "sections": len(sections), "chunks": len(chunks)}


@app.post("/search")
def search(request: SearchRequest) -> dict:
    response = PrecedentSearchService(db).search(
        case_text=request.case_text,
        query=request.query,
        top_k=request.top_k,
    )
    return response.model_dump()
