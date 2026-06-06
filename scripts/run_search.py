from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from precedentiq.data.database import PrecedentIQDB
from precedentiq.services.search_service import PrecedentSearchService


DEFAULT_CASE = """
A tenant was locked out after receiving only an informal email from the landlord.
The landlord claimed renovations made the building unsafe, but no tribunal order
or statutory eviction notice was provided. The tenant seeks damages for hotel
costs, lost property, and wrongful eviction.
"""


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run a PrecedentIQ mock precedent search.")
    parser.add_argument("--case-text", default=DEFAULT_CASE)
    parser.add_argument("--query", default="Find precedents for wrongful eviction without notice")
    parser.add_argument("--top-k", type=int, default=int(os.getenv("PRECEDENTIQ_TOP_K", "5")))
    parser.add_argument("--db-path", default=os.getenv("PRECEDENTIQ_DB_PATH", "precedentiq.sqlite"))
    args = parser.parse_args()

    service = PrecedentSearchService(PrecedentIQDB(args.db_path))
    response = service.search(args.case_text, query=args.query, top_k=args.top_k)

    print(f"Query: {response.query}")
    print(f"Area of law: {response.legal_profile.area_of_law}")
    print()
    for index, precedent in enumerate(response.precedents, start=1):
        case = precedent.case
        print(f"PRECEDENT {index}")
        print(f"Case: {case.case_name}")
        print(f"Citation: {case.citation}")
        print(f"Court: {case.court} | Year: {case.year}")
        print(f"Similarity: {precedent.similarity}")
        print(f"Relevance: {precedent.relevance}")
        print(f"Key finding: {precedent.key_finding}")
        print()
    print(response.disclaimer)


if __name__ == "__main__":
    main()
