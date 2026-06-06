from __future__ import annotations

from precedentiq.models.schemas import (
    LegalProfile,
    PrecedentSummary,
    RankedCase,
    SearchResponse,
)


class PrecedentSummaryGenerator:
    """Deterministic source-grounded summary generator for the mock MVP."""

    def generate(
        self,
        query: str,
        profile: LegalProfile,
        ranked_cases: list[RankedCase],
    ) -> SearchResponse:
        summaries = [
            PrecedentSummary(
                case=ranked_case,
                relevance=self._relevance(profile, ranked_case),
                key_finding=self._key_finding(ranked_case),
                matched_facts=self._matched_facts(profile, ranked_case),
                similarity=self._similarity(ranked_case.case_score),
            )
            for ranked_case in ranked_cases
        ]
        return SearchResponse(query=query, legal_profile=profile, precedents=summaries)

    def _relevance(self, profile: LegalProfile, ranked_case: RankedCase) -> str:
        sections = ", ".join(ranked_case.sections_hit)
        issue = profile.legal_issues[0] if profile.legal_issues else profile.area_of_law
        return (
            f"{ranked_case.case_name} is relevant because its {sections} section(s) "
            f"overlap with the current matter's focus on {issue}. The case was ranked "
            f"using matched text, section coverage, and citation/context signals."
        )

    def _key_finding(self, ranked_case: RankedCase) -> str:
        conclusion = next(
            (section for section in ranked_case.parent_sections if section.section == "Conclusion"),
            None,
        )
        if conclusion:
            return conclusion.text
        best = ranked_case.parent_sections[0] if ranked_case.parent_sections else None
        return best.text[:280] + "..." if best and len(best.text) > 280 else (best.text if best else "")

    def _matched_facts(self, profile: LegalProfile, ranked_case: RankedCase) -> list[str]:
        profile_terms = set(" ".join(profile.key_facts + profile.legal_issues).lower().split())
        facts = []
        for chunk in ranked_case.matched_chunks:
            overlap = profile_terms & set(chunk.text.lower().split())
            if overlap:
                facts.append(chunk.text)
        return facts[:3] or [chunk.text for chunk in ranked_case.matched_chunks[:2]]

    def _similarity(self, score: float) -> str:
        if score >= 0.25:
            return "High"
        if score >= 0.15:
            return "Medium"
        return "Low"
