from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - optional fallback
    BM25Okapi = None

from precedentiq.data.database import PrecedentIQDB
from precedentiq.models.schemas import (
    CaseChunk,
    LegalProfile,
    RankedCase,
    RetrievalCandidate,
)


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]+|\d+")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "without",
    "find",
    "precedents",
    "case",
    "matter",
}

AREA_BOOST_TERMS = {
    "residential tenancy": {"tenant", "tenants", "landlord", "eviction", "evicted", "locked", "notice", "tribunal", "rent"},
    "employment law": {"employee", "employer", "dismissed", "dismissal", "termination", "notice", "just cause"},
    "criminal law": {"accused", "self-defence", "assault", "force", "charter", "police", "arrest"},
    "immigration law": {"immigration", "visa", "applicant", "officer", "procedural", "fairness"},
    "privacy law": {"privacy", "data", "consent", "consumer", "disclosure"},
}


class HybridRetriever:
    def __init__(self, db: PrecedentIQDB) -> None:
        self.db = db

    def search(self, profile: LegalProfile, top_k: int = 5) -> list[RankedCase]:
        chunks = self.db.fetch_chunks()
        query = profile.retrieval_query()
        semantic = self._lexical_semantic_search(query, chunks, top_n=20)
        bm25 = self._bm25_search(query, chunks, top_n=20)
        citation = self._citation_search(profile.cases_cited, chunks)
        fused = self._rrf_merge([semantic, bm25, citation])
        boosted = self._citation_boost(fused, profile.cases_cited)
        boosted = self._area_boost(boosted, profile.area_of_law)
        return self._group_cases(boosted, top_k=top_k)

    def _lexical_semantic_search(
        self, query: str, chunks: list[CaseChunk], top_n: int
    ) -> list[RetrievalCandidate]:
        query_terms = Counter(tokenize(query))
        candidates = []
        for chunk in chunks:
            chunk_terms = Counter(tokenize(chunk.text))
            score = cosine_counter(query_terms, chunk_terms)
            if score > 0:
                candidates.append(RetrievalCandidate(chunk=chunk, score=score, source="semantic"))
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_n]

    def _bm25_search(
        self, query: str, chunks: list[CaseChunk], top_n: int
    ) -> list[RetrievalCandidate]:
        tokenized_chunks = [tokenize(chunk.text) for chunk in chunks]
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        if BM25Okapi:
            model = BM25Okapi(tokenized_chunks)
            scores = model.get_scores(query_tokens)
        else:
            scores = [sum(1 for token in query_tokens if token in chunk_tokens) for chunk_tokens in tokenized_chunks]

        candidates = [
            RetrievalCandidate(chunk=chunk, score=float(score), source="bm25")
            for chunk, score in zip(chunks, scores)
            if score > 0
        ]
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_n]

    def _citation_search(
        self, query_citations: list[str], chunks: list[CaseChunk]
    ) -> list[RetrievalCandidate]:
        if not query_citations:
            return []
        query_set = set(query_citations)
        candidates = []
        for chunk in chunks:
            overlap = len(query_set & set(chunk.cited_cases + [chunk.citation]))
            if overlap:
                candidates.append(
                    RetrievalCandidate(chunk=chunk, score=float(overlap), source="citation")
                )
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:20]

    def _rrf_merge(self, result_sets: list[list[RetrievalCandidate]], k: int = 60) -> list[RetrievalCandidate]:
        scores: dict[str, float] = defaultdict(float)
        chunks_by_id: dict[str, CaseChunk] = {}
        sources: dict[str, list[str]] = defaultdict(list)

        for result_set in result_sets:
            for rank, candidate in enumerate(result_set, start=1):
                scores[candidate.chunk.id] += 1 / (k + rank)
                chunks_by_id[candidate.chunk.id] = candidate.chunk
                sources[candidate.chunk.id].append(candidate.source)

        merged = [
            RetrievalCandidate(
                chunk=chunks_by_id[chunk_id],
                score=score,
                source="+".join(sorted(set(sources[chunk_id]))),
            )
            for chunk_id, score in scores.items()
        ]
        return sorted(merged, key=lambda item: item.score, reverse=True)[:30]

    def _citation_boost(
        self, candidates: list[RetrievalCandidate], query_citations: list[str]
    ) -> list[RetrievalCandidate]:
        query_set = set(query_citations)
        if not query_set:
            return candidates
        boosted = []
        for candidate in candidates:
            overlap = len(query_set & set(candidate.chunk.cited_cases + [candidate.chunk.citation]))
            candidate.score += overlap * 0.05
            boosted.append(candidate)
        return sorted(boosted, key=lambda item: item.score, reverse=True)

    def _area_boost(
        self, candidates: list[RetrievalCandidate], area_of_law: str
    ) -> list[RetrievalCandidate]:
        terms = AREA_BOOST_TERMS.get(area_of_law, set())
        if not terms:
            return candidates
        boosted = []
        for candidate in candidates:
            text = f"{candidate.chunk.case_name} {candidate.chunk.text}".lower()
            matches = sum(1 for term in terms if term in text)
            candidate.score += min(matches * 0.04, 0.25)
            boosted.append(candidate)
        return sorted(boosted, key=lambda item: item.score, reverse=True)

    def _group_cases(self, candidates: list[RetrievalCandidate], top_k: int) -> list[RankedCase]:
        grouped: dict[str, list[RetrievalCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.chunk.citation].append(candidate)

        ranked = []
        for citation, case_candidates in grouped.items():
            chunks = [candidate.chunk for candidate in case_candidates]
            sections_hit = sorted(set(chunk.section for chunk in chunks))
            best_score = max(candidate.score for candidate in case_candidates)
            year = chunks[0].year
            recency_score = 1 / max(1, 2026 - year + 1)
            citation_overlap = max(len(set(chunk.cited_cases) & {c.citation for c in chunks}) for chunk in chunks)
            case_score = best_score * 0.65 + len(sections_hit) * 0.08 + recency_score * 0.15

            parent_ids = list(dict.fromkeys(chunk.parent_section_id for chunk in chunks))
            parent_sections = self.db.fetch_sections_by_ids(parent_ids)
            ranked.append(
                RankedCase(
                    citation=citation,
                    case_name=chunks[0].case_name,
                    court=chunks[0].court,
                    year=year,
                    source_url=chunks[0].source_url,
                    case_score=round(case_score, 4),
                    best_chunk_score=round(best_score, 4),
                    sections_hit=sections_hit,
                    citation_overlap=citation_overlap,
                    matched_chunks=chunks[:3],
                    parent_sections=parent_sections,
                )
            )

        return sorted(ranked, key=lambda item: item.case_score, reverse=True)[:top_k]


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    ]


def cosine_counter(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    intersection = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in intersection)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
