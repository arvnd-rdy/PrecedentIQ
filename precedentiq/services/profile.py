from __future__ import annotations

import re

from precedentiq.models.schemas import LegalProfile
from precedentiq.services.ingestion import extract_citations


AREA_KEYWORDS = {
    "criminal law": {"accused", "assault", "self-defence", "charter", "police", "arrest"},
    "employment law": {"dismissed", "employee", "employer", "termination", "notice", "just cause"},
    "immigration law": {"visa", "immigration", "application", "officer", "permanent residence"},
    "privacy law": {"privacy", "data", "consent", "personal information", "disclosure"},
    "residential tenancy": {"tenant", "landlord", "eviction", "rent", "notice to vacate"},
    "administrative law": {"tribunal", "reasonableness", "judicial review", "procedural fairness"},
}

STATUTE_PATTERN = re.compile(
    r"\b(?:Criminal Code|Charter|Residential Tenancies Act|Privacy Act|PIPEDA)\s*(?:s\.?\s*\d+)?",
    re.IGNORECASE,
)


class LegalProfileExtractor:
    """Deterministic legal profile extractor for the mock-data MVP."""

    def extract(self, text: str, query: str = "") -> LegalProfile:
        combined = f"{query}\n{text}".strip()
        normalized = combined.lower()
        area = self._detect_area(normalized)
        sentences = self._sentences(combined)
        key_facts = self._select_sentences(sentences, limit=4)
        legal_issues = self._extract_issues(sentences, area)
        statutes = sorted(set(match.group(0).strip() for match in STATUTE_PATTERN.finditer(combined)))
        cases_cited = extract_citations(combined)

        return LegalProfile(
            area_of_law=area,
            key_facts=key_facts,
            legal_issues=legal_issues,
            statutes_mentioned=statutes,
            cases_cited=cases_cited,
        )

    def _detect_area(self, normalized: str) -> str:
        scores = {
            area: sum(1 for keyword in keywords if keyword in normalized)
            for area, keywords in AREA_KEYWORDS.items()
        }
        best_area, best_score = max(scores.items(), key=lambda item: item[1])
        return best_area if best_score > 0 else "general legal research"

    def _sentences(self, text: str) -> list[str]:
        return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]

    def _select_sentences(self, sentences: list[str], limit: int) -> list[str]:
        useful = [
            sentence
            for sentence in sentences
            if len(sentence.split()) >= 5 and not sentence.lower().startswith("find ")
        ]
        return useful[:limit] or sentences[:limit]

    def _extract_issues(self, sentences: list[str], area: str) -> list[str]:
        issue_sentences = [
            sentence
            for sentence in sentences
            if any(term in sentence.lower() for term in ("whether", "issue", "breach", "reasonable", "notice", "consent"))
        ]
        if issue_sentences:
            return issue_sentences[:3]
        return [f"Find relevant precedents in {area} with similar facts and legal issues."]
