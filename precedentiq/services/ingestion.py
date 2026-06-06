from __future__ import annotations

import json
import re
from pathlib import Path

from precedentiq.data.database import PrecedentIQDB
from precedentiq.models.schemas import CaseChunk, CaseSection, LegalCase, SectionName


SECTION_NAMES: tuple[SectionName, ...] = (
    "Header",
    "Overview",
    "Facts",
    "Issues",
    "Analysis",
    "Conclusion",
)

CITATION_PATTERN = re.compile(
    r"\b\d{4}\s+(?:SCC|ONCA|BCCA|FCA|NSCA|ABCA|MBCA|SKCA)\s+\d+\b"
)


class CaseIngestionService:
    def __init__(self, db: PrecedentIQDB) -> None:
        self.db = db

    def load_sample_cases(self) -> list[LegalCase]:
        sample_path = Path(__file__).parents[1] / "data" / "sample_cases.json"
        raw_cases = json.loads(sample_path.read_text(encoding="utf-8"))
        return [LegalCase.model_validate(case) for case in raw_cases]

    def ingest_sample_corpus(self) -> tuple[list[LegalCase], list[CaseSection], list[CaseChunk]]:
        cases = self.load_sample_cases()
        sections: list[CaseSection] = []
        chunks: list[CaseChunk] = []

        for case in cases:
            parsed_sections = self.parse_sections(case)
            sections.extend(parsed_sections)
            for section in parsed_sections:
                chunks.extend(self.chunk_section(section))

        self.db.save_cases(cases)
        self.db.save_sections(sections)
        self.db.save_chunks(chunks)
        return cases, sections, chunks

    def parse_sections(self, case: LegalCase) -> list[CaseSection]:
        text = case.unofficial_text
        pattern = re.compile(r"^(Header|Overview|Facts|Issues|Analysis|Conclusion)\s*$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        sections: list[CaseSection] = []

        for index, match in enumerate(matches):
            section_name = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            if not section_text:
                continue
            section_id = f"{case.citation.replace(' ', '-')}-{section_name.lower()}"
            cited_cases = sorted(set(case.cited_cases + extract_citations(section_text)))
            sections.append(
                CaseSection(
                    id=section_id,
                    citation=case.citation,
                    case_name=case.name,
                    court=case.court,
                    year=case.year,
                    source_url=case.source_url,
                    section=section_name,  # type: ignore[arg-type]
                    text=section_text,
                    cited_cases=cited_cases,
                )
            )
        return sections

    def chunk_section(self, section: CaseSection, max_words: int = 110) -> list[CaseChunk]:
        words = section.text.split()
        if len(words) <= max_words:
            chunks_text = [section.text]
        else:
            chunks_text = []
            step = max_words - 20
            for start in range(0, len(words), step):
                chunks_text.append(" ".join(words[start : start + max_words]))

        total = len(chunks_text)
        return [
            CaseChunk(
                id=f"{section.id}-chunk-{index + 1}",
                parent_section_id=section.id,
                citation=section.citation,
                case_name=section.case_name,
                court=section.court,
                year=section.year,
                source_url=section.source_url,
                section=section.section,
                chunk_index=index + 1,
                total_chunks=total,
                text=chunk_text,
                cited_cases=section.cited_cases,
            )
            for index, chunk_text in enumerate(chunks_text)
        ]


def extract_citations(text: str) -> list[str]:
    return sorted(set(CITATION_PATTERN.findall(text)))
