from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


SectionName = Literal["Header", "Overview", "Facts", "Issues", "Analysis", "Conclusion"]


class LegalCase(BaseModel):
    citation: str
    citation2: str | None = None
    court: str
    year: int
    name: str
    language: str = "en"
    document_date: date
    source_url: str
    unofficial_text: str
    cited_cases: list[str] = Field(default_factory=list)


class CaseSection(BaseModel):
    id: str
    citation: str
    case_name: str
    court: str
    year: int
    source_url: str
    section: SectionName
    text: str
    cited_cases: list[str] = Field(default_factory=list)


class CaseChunk(BaseModel):
    id: str
    parent_section_id: str
    citation: str
    case_name: str
    court: str
    year: int
    source_url: str
    section: SectionName
    chunk_index: int
    total_chunks: int
    text: str
    cited_cases: list[str] = Field(default_factory=list)


class LegalProfile(BaseModel):
    area_of_law: str
    key_facts: list[str]
    legal_issues: list[str]
    statutes_mentioned: list[str] = Field(default_factory=list)
    cases_cited: list[str] = Field(default_factory=list)
    jurisdiction: str = "Canada"
    procedural_posture: str = "appeal"

    def retrieval_query(self) -> str:
        parts = [
            self.area_of_law,
            " ".join(self.key_facts),
            " ".join(self.legal_issues),
            " ".join(self.statutes_mentioned),
            " ".join(self.cases_cited),
        ]
        return " ".join(part for part in parts if part).strip()


class RetrievalCandidate(BaseModel):
    chunk: CaseChunk
    score: float
    source: str


class RankedCase(BaseModel):
    citation: str
    case_name: str
    court: str
    year: int
    source_url: str
    case_score: float
    best_chunk_score: float
    sections_hit: list[str]
    citation_overlap: int
    matched_chunks: list[CaseChunk]
    parent_sections: list[CaseSection]


class PrecedentSummary(BaseModel):
    case: RankedCase
    relevance: str
    key_finding: str
    matched_facts: list[str]
    similarity: Literal["High", "Medium", "Low"]


class SearchResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    legal_profile: LegalProfile
    precedents: list[PrecedentSummary]
    disclaimer: str = (
        "This is a research aid only. Not legal advice. Always verify citations "
        "against official sources and consult a qualified legal professional."
    )
