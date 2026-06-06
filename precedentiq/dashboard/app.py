from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from precedentiq.data.database import PrecedentIQDB
from precedentiq.services.search_service import PrecedentSearchService

load_dotenv()

DEFAULT_CASE = """
A tenant was locked out after receiving only an informal email from the landlord.
The landlord claimed renovations made the building unsafe, but no tribunal order
or statutory eviction notice was provided. The tenant seeks damages for hotel
costs, lost property, and wrongful eviction.
"""

st.set_page_config(page_title="PrecedentIQ", layout="wide")
st.title("PrecedentIQ")
st.caption("Canadian legal precedent retrieval engine")

with st.sidebar:
    st.header("Search Controls")
    top_k = st.slider("Top precedents", min_value=1, max_value=5, value=5)
    db_path = st.text_input("Database path", os.getenv("PRECEDENTIQ_DB_PATH", "precedentiq.sqlite"))

case_text = st.text_area("Current Case / Fact Pattern", value=DEFAULT_CASE, height=220)
query = st.text_input("Research Query", value="Find precedents for wrongful eviction without notice")

if st.button("Find Precedents", type="primary"):
    service = PrecedentSearchService(PrecedentIQDB(db_path))
    response = service.search(case_text=case_text, query=query, top_k=top_k)

    st.subheader("Extracted Legal Profile")
    profile = response.legal_profile
    col1, col2 = st.columns(2)
    col1.write(f"**Area of law:** {profile.area_of_law}")
    col2.write(f"**Jurisdiction:** {profile.jurisdiction}")
    st.write("**Legal issues:**")
    for issue in profile.legal_issues:
        st.write(f"- {issue}")

    st.subheader("Ranked Precedents")
    for index, precedent in enumerate(response.precedents, start=1):
        case = precedent.case
        with st.expander(f"{index}. {case.case_name} ({case.citation}) - {precedent.similarity}", expanded=index == 1):
            st.write(f"**Court:** {case.court}")
            st.write(f"**Year:** {case.year}")
            st.write(f"**Case score:** {case.case_score}")
            st.write(f"**Sections hit:** {', '.join(case.sections_hit)}")
            st.write(f"**Relevance:** {precedent.relevance}")
            st.write(f"**Key finding:** {precedent.key_finding}")
            st.write("**Matched facts / passages:**")
            for fact in precedent.matched_facts:
                st.info(fact)
            st.link_button("Open source", case.source_url)

    st.warning(response.disclaimer)
else:
    st.info("Paste a fact pattern and click Find Precedents to run the mock RAG pipeline.")
