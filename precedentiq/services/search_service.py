from __future__ import annotations

from precedentiq.data.database import PrecedentIQDB
from precedentiq.models.schemas import SearchResponse
from precedentiq.retrieval.search import HybridRetriever
from precedentiq.services.generation import PrecedentSummaryGenerator
from precedentiq.services.ingestion import CaseIngestionService
from precedentiq.services.profile import LegalProfileExtractor


class PrecedentSearchService:
    def __init__(self, db: PrecedentIQDB) -> None:
        self.db = db
        self.ingestion = CaseIngestionService(db)
        self.profile_extractor = LegalProfileExtractor()
        self.retriever = HybridRetriever(db)
        self.generator = PrecedentSummaryGenerator()

    def ensure_sample_index(self) -> None:
        if not self.db.fetch_chunks():
            self.ingestion.ingest_sample_corpus()

    def search(self, case_text: str, query: str = "", top_k: int = 5) -> SearchResponse:
        self.ensure_sample_index()
        profile = self.profile_extractor.extract(case_text, query=query)
        ranked_cases = self.retriever.search(profile, top_k=top_k)
        return self.generator.generate(
            query=query or case_text[:120],
            profile=profile,
            ranked_cases=ranked_cases,
        )
