from __future__ import annotations

from precedentiq.data.database import PrecedentIQDB
from precedentiq.services.search_service import PrecedentSearchService


def test_wrongful_eviction_query_returns_tenancy_case(tmp_path):
    service = PrecedentSearchService(PrecedentIQDB(tmp_path / "precedentiq-test.sqlite"))
    response = service.search(
        case_text=(
            "A tenant was locked out after an informal email. No statutory notice "
            "or tribunal order was provided. The tenant seeks damages for wrongful eviction."
        ),
        query="Find precedents for wrongful eviction without notice",
    )

    assert response.precedents
    assert response.legal_profile.area_of_law == "residential tenancy"
    assert response.precedents[0].case.citation == "2017 SCC 41"
