# PrecedentIQ

**PrecedentIQ** is a Canadian legal precedent retrieval engine that helps legal professionals surface relevant case law from Supreme Court of Canada decisions using hybrid search, citation signals, case-level ranking, and retrieval-augmented generation.

> This project is designed as a portfolio-grade AI engineering system. It is a legal research aid, not a legal advice product.

## Problem

Legal research often requires finding the right precedent across decades of long, dense court decisions. Generic LLMs can explain legal concepts, but they cannot reliably retrieve source-grounded Canadian case law, verify citations, rank precedents at the case level, or reason over citation relationships without an indexed legal corpus.

PrecedentIQ focuses on the retrieval problem:

- Given a current legal case or fact pattern, find similar past Canadian rulings.
- Return ranked case-level results, not isolated text chunks.
- Explain why each precedent is relevant using matched facts, legal issues, and source citations.
- Reduce hallucinated citations through metadata verification and source-grounded generation.

## Core Features

- **Section-aware legal ingestion** for long court judgments, preserving Facts, Issues, Analysis, and Conclusion sections.
- **Hybrid retrieval** combining dense semantic search, BM25 keyword matching, citation matching, and Reciprocal Rank Fusion.
- **Citation graph boosting** to surface cases sharing authorities with the uploaded matter.
- **Case-level ranking** to group retrieved chunks by citation and rank full precedents instead of returning duplicate chunks.
- **Cross-encoder reranking** using Cohere Rerank to refine candidate results before generation.
- **Structured RAG output** with matched facts, key findings, citations, and relevance explanations.
- **Evaluation plan** using Recall@5, MRR, nDCG@10, RAGAs, duplicate-case rate, and citation hallucination rate.
- **Observability** with Langfuse traces for retrieval, reranking, generation, latency, cost, and hallucination checks.

## Dataset

PrecedentIQ is designed around the open `a2aj/canadian-case-law` dataset on Hugging Face.

MVP scope:

- **Court:** Supreme Court of Canada
- **Volume:** 15K+ decisions
- **Language:** English only
- **Document type:** appellate court rulings

The full dataset includes 116K+ Canadian court decisions across SCC, FCA, ONCA, BCCA, NSCA, and other courts.

## Architecture Overview

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
Parent-Child Section Expansion
        ↓
Claude Structured Generation
        ↓
Citation Verification + Guardrails
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full system design.

## Retrieval Strategy

PrecedentIQ does not rely on vector search alone. Legal retrieval requires exact terms, statutes, citations, and authority relationships.

The retrieval pipeline combines:

- **Dense retrieval:** `BAAI/bge-large-en-v1.5` embeddings over section-aware chunks.
- **Sparse retrieval:** BM25 for exact legal terms, statute sections, Latin terms, and citations.
- **Citation retrieval:** direct matching and shared-authority boosting from extracted case citations.
- **Reranking:** cross-encoder reranking over the merged candidate set.
- **Case-level scoring:** ranking full cases by best chunk score, section coverage, recency, and citation overlap.

## Evaluation Targets

Planned MVP evaluation uses a hand-built legal retrieval test set.

| Metric | Target |
|---|---:|
| Recall@5 | > 0.70 |
| MRR | > 0.60 |
| nDCG@10 | > 0.65 |
| Duplicate case result rate | 0% |
| Citation hallucination rate | < 5% |
| RAGAs faithfulness | > 0.80 |

Example iteration goal:

> Improve Recall@5 from 0.52 to 0.74 by moving from baseline vector search to hybrid retrieval with citation boosting and case-level grouping.

## Tech Stack

| Layer | Tools |
|---|---|
| Language | Python 3.11 |
| API | FastAPI |
| UI | Streamlit |
| Dataset | Hugging Face Datasets, A2AJ Canadian Case Law |
| Embeddings | Sentence Transformers, `BAAI/bge-large-en-v1.5` |
| Vector DB | ChromaDB for local MVP, Pinecone optional for deployment |
| Keyword Search | BM25 |
| Reranking | Cohere Rerank |
| LLM | Claude 3.5 Sonnet |
| Observability | Langfuse |
| Evaluation | custom IR metrics, RAGAs |

## Roadmap

- Build SCC-only MVP with English decisions.
- Add ONCA, FCA, and BCCA collections.
- Add full citation treatment history: followed, distinguished, criticized, overturned.
- Add multilingual retrieval for French-language decisions.
- Integrate statutes as supporting context.
- Add deployed demo with query traces and evaluation dashboard.

## Disclaimer

PrecedentIQ is a research and portfolio project. It is not legal advice and should not be relied on in legal proceedings without verification by a qualified legal professional.

Data is sourced from A2AJ and subject to the dataset's licensing terms, including non-commercial restrictions where applicable.
