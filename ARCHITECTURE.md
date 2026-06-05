# PrecedentIQ Architecture

## 1. Product Summary

PrecedentIQ is a Canadian legal precedent retrieval engine. A user uploads a current case, legal memo, or fact pattern, and the system retrieves similar Canadian rulings with citations, matched facts, legal issues, and relevance explanations.

The system is intentionally framed as a retrieval engine, not a legal chatbot. The core technical problem is finding the right precedent from a large corpus of long court decisions, then explaining the relevance without inventing citations or legal claims.

## 2. Problem Statement

Legal professionals spend significant time searching through past decisions to find cases with similar facts, issues, statutes, or reasoning. Generic LLMs are weak at this task because they do not have guaranteed access to the target corpus, cannot reliably verify citations, and do not naturally rank precedents by court authority or case-level relevance.

PrecedentIQ solves this by combining:

- Legal document ingestion
- Section-aware chunking
- Hybrid semantic and keyword retrieval
- Citation graph signals
- Cross-encoder reranking
- Case-level scoring
- Source-grounded LLM generation
- Evaluation and observability

## 3. Data Sources

### 3.1 Case Law

Primary source: `a2aj/canadian-case-law` on Hugging Face.

The dataset includes approximately 116K Canadian court decisions with metadata such as:

- citation
- court
- year
- case name
- language
- document date
- source URL
- full unofficial decision text

### 3.2 MVP Scope

The MVP starts with Supreme Court of Canada decisions only.

Reasons:

- SCC rulings carry the strongest precedent value.
- The corpus is large enough to validate retrieval quality.
- SCC decisions are usually well-structured and citation-rich.
- Starting smaller makes evaluation and iteration practical.

MVP filters:

- `dataset == "SCC"`
- `language == "en"`
- `len(unofficial_text) > 500`

### 3.3 Statutes

Statutes are out of scope for MVP. They can be added in a later version using:

- `a2aj/canadian-laws`
- Justice Canada XML
- provincial law sources

The primary MVP value is case retrieval, not statute explanation.

## 4. Offline Ingestion Pipeline

The offline pipeline prepares the legal corpus for retrieval.

```text
A2AJ Dataset
    ↓
English + non-empty filtering
    ↓
Citation extraction
    ↓
Section-aware parsing
    ↓
Chunking + parent section storage
    ↓
Embedding generation
    ↓
Vector index + BM25 index + citation index
```

### 4.1 Citation Extraction

During ingestion, citations are extracted from every decision to create a lightweight citation index.

Example neutral citations:

- `2023 SCC 15`
- `2019 ONCA 44`
- `2021 FCA 100`

Example extraction pattern:

```python
pattern = r"\b\d{4}\s+(?:SCC|ONCA|BCCA|FCA|NSCA|ABCA|MBCA|SKCA)\s+\d+\b"
```

The output is stored as:

```json
{
  "2023 SCC 15": ["2019 SCC 4", "2015 ONCA 22"]
}
```

This powers citation overlap and shared-authority boosting during retrieval.

## 5. Chunking Strategy

Legal judgments are long and structured. Naive fixed-size chunking can mix unrelated sections or cut important reasoning in half.

PrecedentIQ uses section-aware chunking.

### 5.1 Expected Judgment Structure

Typical sections:

- Header
- Overview
- Facts / Background
- Issues
- Analysis / Reasons
- Conclusion / Disposition

### 5.2 Section Detection

The parser detects legal section headings such as:

- `Facts`
- `Background`
- `The Facts`
- `Issues`
- `Analysis`
- `Discussion`
- `Reasons`
- `Conclusion`
- `Decision`
- `Disposition`

It also supports numbered and Roman numeral headings where possible.

### 5.3 Chunk Rules

| Section | Strategy |
|---|---|
| Header | Keep as one short metadata-rich chunk |
| Overview | Keep as one chunk |
| Facts | Split into 300-400 token paragraph groups |
| Issues | Keep as one chunk when short |
| Analysis | Split into 300-500 token paragraph groups |
| Conclusion | Keep as one chunk |

Each chunk stores metadata:

```json
{
  "case_name": "R. v. Smith",
  "citation": "2023 SCC 15",
  "court": "SCC",
  "year": 2023,
  "date": "2023-04-12",
  "section": "Facts",
  "chunk_index": 2,
  "total_chunks": 8,
  "source_url": "https://...",
  "cited_cases": ["2019 SCC 4", "2015 ONCA 22"]
}
```

### 5.4 Parent-Child Retrieval

Small chunks are used for precise retrieval, but each chunk points to its full parent section. The LLM receives the full parent section for context after retrieval and reranking.

This avoids showing users tiny isolated snippets that lack enough legal context.

## 6. Embedding Strategy

Default embedding model:

```text
BAAI/bge-large-en-v1.5
```

Reasons:

- Optimized for retrieval and semantic similarity.
- Strong general-purpose embedding performance.
- Free and local.
- More appropriate for retrieval than legal base language models used without sentence-embedding fine-tuning.

Important note:

Legal-BERT is a domain-specific base language model, but it is not automatically a strong retrieval embedding model. PrecedentIQ treats Legal-BERT as a comparison baseline, not the default choice.

### 6.1 Embedding Comparison

The README and evaluation should compare:

- `BAAI/bge-large-en-v1.5`
- `nlpaueb/legal-bert-base-uncased`
- `text-embedding-3-small`

The final model should be justified by retrieval metrics such as Recall@5 and MRR.

## 7. Retrieval Architecture

The retrieval pipeline is the core of the system.

```text
Uploaded Case / Query
    ↓
Structured Legal Profile Extraction
    ↓
Semantic Search + BM25 + Citation Matching
    ↓
Reciprocal Rank Fusion
    ↓
Citation Graph Boost
    ↓
Cohere Rerank
    ↓
Case-Level Grouping + Scoring
    ↓
Parent-Child Expansion
    ↓
LLM Generation
```

### 7.1 Structured Legal Profile Extraction

Before retrieval, the uploaded case is converted into a structured legal profile.

Example schema:

```json
{
  "area_of_law": "criminal law",
  "key_facts": [
    "accused claimed self-defence",
    "physical altercation occurred after verbal threat"
  ],
  "legal_issues": [
    "whether force used was reasonable",
    "application of Criminal Code self-defence provisions"
  ],
  "statutes_mentioned": ["Criminal Code s. 34"],
  "cases_cited": ["2009 SCC 32"],
  "jurisdiction": "Canada",
  "procedural_posture": "appeal"
}
```

This is more reliable than simple query expansion because it separates facts, issues, statutes, citations, and procedural context.

### 7.2 Semantic Search

The dense query is built from:

- key facts
- legal issues
- statute references
- procedural posture

The query is embedded and searched against section-aware chunks.

Returns:

```text
top 20 semantic chunks
```

### 7.3 BM25 Keyword Search

BM25 catches exact matches that embeddings can miss:

- statute sections
- neutral citations
- legal terms
- Latin phrases
- party names
- specific doctrinal language

Returns:

```text
top 20 keyword chunks
```

### 7.4 Citation Matching

If the uploaded case cites known authorities, PrecedentIQ looks for indexed cases that cite the same authorities.

This finds cases connected by legal reasoning, even when the surface language differs.

Returns:

```text
direct citation-overlap candidates
```

### 7.5 Reciprocal Rank Fusion

Semantic, BM25, and citation results are merged using Reciprocal Rank Fusion.

Formula:

```text
score = 1 / (k + rank)
```

This produces a stable combined ranking without over-trusting one retrieval method.

### 7.6 Citation Graph Boost

After RRF, candidates receive a score boost if they share cited authorities with the uploaded case.

Example:

```python
boost = shared_authority_count * 0.1
```

This is intentionally lightweight in the MVP. Full citation treatment analysis is reserved for V2.

### 7.7 Cross-Encoder Reranking

The top 30 candidates are reranked with Cohere Rerank.

Reason:

- Bi-encoder retrieval is fast but approximate.
- Cross-encoder reranking evaluates query-document relevance more directly.
- This improves final precision before LLM generation.

### 7.8 Case-Level Grouping

Most RAG systems rank chunks. PrecedentIQ ranks cases.

After reranking, chunks are grouped by citation.

Case score uses:

- best chunk relevance
- number of matched sections
- recency
- citation overlap
- court authority

Example scoring:

```python
case_score = (
    best_chunk_score * 0.60 +
    section_breadth_score * 0.20 +
    recency_score * 0.10 +
    citation_overlap_score * 0.10
)
```

This prevents one case with many similar chunks from dominating the result list.

## 8. LLM Generation Layer

The LLM does not search the law by itself. It only explains already-retrieved cases.

Input:

- structured current case profile
- top 5 ranked cases
- parent sections for each case
- metadata and citations

Output:

- case name
- citation
- court
- date
- relevance explanation
- matched facts
- key finding
- law cited
- similarity label
- summary
- disclaimer

### 8.1 Generation Rules

The prompt enforces:

- Only reference retrieved cases.
- Never invent citations.
- Do not provide legal advice.
- Flag old cases.
- Cite every case by neutral citation.
- Explain relevance using retrieved text.

## 9. Guardrails

### 9.1 Input Guardrails

Checks:

- language is English
- uploaded text has enough content
- query is legal-research related
- document appears to be legal or case-like

### 9.2 Output Guardrails

Checks:

- citation verification against retrieved metadata
- disclaimer presence
- response completeness
- unverified citation warning

Citation verification:

```python
found = re.findall(r"\d{4}\s+[A-Z]+\s+\d+", response_text)
hallucinated = [c for c in found if c not in valid_citations]
```

If unverified citations are found, the UI flags them instead of silently hiding the response.

## 10. Observability

Langfuse traces every request.

Trace structure:

```text
precedent_search
├── legal_profile_extraction
├── semantic_search
├── bm25_search
├── citation_matching
├── rrf_merge
├── citation_boost
├── reranking
├── case_grouping
├── llm_generation
└── citation_verification
```

Tracked metrics:

- retrieval latency
- reranking latency
- generation latency
- token usage
- cost
- top retrieved citations
- rerank scores
- case-level scores
- hallucinated citation count
- duplicate-case rate

## 11. Evaluation

PrecedentIQ uses two evaluation layers: retrieval quality and generation quality.

### 11.1 Retrieval Evaluation

Primary metrics:

| Metric | Purpose |
|---|---|
| Recall@5 | Whether a known relevant case appears in top 5 |
| MRR | How high the first relevant case appears |
| nDCG@10 | Whether better cases rank near the top |
| Duplicate-case rate | Whether chunk-level duplication leaks into results |

Planned benchmark:

- 30 hand-built legal retrieval queries
- each query has known relevant cases
- compare baseline vector search against hybrid retrieval and case-level grouping

Target iteration:

```text
Recall@5: 0.52 baseline → 0.74 after hybrid retrieval + citation boost + case grouping
Duplicate-case rate: 0%
```

### 11.2 Generation Evaluation

RAGAs metrics:

- faithfulness
- answer relevancy
- context precision
- context recall

Custom checks:

- citation hallucination rate
- disclaimer presence
- matched facts grounded in retrieved text

Target:

```text
Citation hallucination rate < 5%
RAGAs faithfulness > 0.80
```

## 12. API Design

Planned FastAPI endpoints:

```text
POST /cases/upload
Upload current case text.

POST /search
Run precedent retrieval.

GET /search/{search_id}
Fetch search result.

GET /cases/{citation}
Fetch case metadata and sections.

GET /eval/runs
Fetch evaluation history.
```

## 13. Frontend

Planned MVP UI with Streamlit:

- Upload case text
- Enter optional query
- Select court/year filters
- View top precedent cards
- Inspect matched facts and source sections
- View citations and source URLs
- Display warning for unverified citations

## 14. Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| API | FastAPI |
| UI | Streamlit |
| Data | Hugging Face Datasets |
| Embeddings | Sentence Transformers, BGE |
| Vector DB | ChromaDB locally, Pinecone optionally |
| Keyword Search | BM25 |
| Reranking | Cohere Rerank |
| LLM | Claude 3.5 Sonnet |
| Observability | Langfuse |
| Evaluation | custom IR metrics, RAGAs |

## 15. V2 Roadmap

### 15.1 Full Citation Treatment Graph

MVP uses citation overlap and shared authorities. V2 adds treatment analysis:

- followed
- distinguished
- criticized
- overruled
- reversed

### 15.2 More Courts

Add:

- ONCA
- FCA
- BCCA
- NSCA
- provincial appellate courts

### 15.3 French-Language Retrieval

Add multilingual embeddings and French case retrieval.

Potential models:

- `intfloat/multilingual-e5-large`
- `BAAI/bge-m3`

### 15.4 Statute Integration

Index statutes as supporting context and connect cases to legislative provisions.

### 15.5 Production Deployment

Add:

- Docker
- PostgreSQL
- Pinecone or managed vector DB
- CI pipeline
- hosted demo

## 16. Key Design Decisions

### Why not generic legal chatbot?

Because the value is not legal conversation. The value is finding source-grounded precedents from a large legal corpus.

### Why hybrid retrieval?

Legal search needs both semantic similarity and exact matching for statutes, citations, and doctrinal language.

### Why case-level ranking?

Users need relevant cases, not duplicate chunks from the same decision.

### Why citation signals?

Citation overlap captures legal authority relationships that embeddings do not.

### Why structured profile extraction?

It separates facts, issues, statutes, and citations, making retrieval more precise than a single expanded query string.

### Why evaluate with IR metrics?

The core product claim is retrieval quality. Recall@5, MRR, and nDCG measure whether the right precedents are actually surfaced.
