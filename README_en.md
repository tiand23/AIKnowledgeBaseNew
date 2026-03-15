# AI Knowledge Base Platform

This document is the user-focused guide for international readers.  
For architecture/deep design review, see [docs/architecture_ja.md](./docs/architecture_ja.md).

## 1. What You Can Do
- Upload documents in chunks and process them asynchronously
- Build page-level visual assets for all supported documents
- Parse image-heavy documents with VLM-assisted structuring
- Ask questions with text + visual + graph retrieval
- Enforce access boundaries by owner/public/org/default
- Store evaluation data for continuous quality improvement

## 2. Typical Use Cases
- Cross-document search across design specs and operation manuals
- Organization-scoped knowledge sharing with access control
- Ongoing answer quality improvement using evaluation metrics

## 3. Quick Start (Docker)
1. Create config file:
```bash
cp .env.example .env
```
2. Edit `.env` (at minimum set `OPENAI_API_KEY` and passwords)
3. Start services:
```bash
cd app
./start_docker.sh pg up
```
4. Verify health:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl http://localhost:8000/health
```
5. Stop services:
```bash
cd app
./start_docker.sh pg down
```

## 4. Minimal User Flow
1. Register account (org tags / primary org)
2. Upload documents (scope + org tag)
3. Ask in Knowledge Q&A
4. Verify answer with evidence links/images

## 5. System Overview
```mermaid
flowchart LR
    U["User / Frontend"]
    API["FastAPI API"]
    K["Kafka"]
    DP["Document Processor"]
    QA["Q&A Orchestrator"]

    subgraph STORE["Storage / Index Layer"]
        OBJ["MinIO\nRaw files / page PNG / evidence"]
        PG["PostgreSQL\nmetadata / ACL / units / chunks / VLM meta"]
        AGE["PostgreSQL + AGE\nGraph store"]
        ES_T["Elasticsearch\nText Index"]
        ES_V["Elasticsearch\nVisual Index"]
    end

    subgraph MODEL["Model Layer"]
        TXT_EMB["OpenAI Text Embedding"]
        VIS_EMB["Gemini Visual Embedding"]
        VLM["VLM"]
        LLM["LLM Answering"]
    end

    U --> API
    API --> K
    K --> DP

    DP --> OBJ
    DP --> PG
    DP --> TXT_EMB
    DP --> VIS_EMB
    DP --> VLM

    TXT_EMB --> ES_T
    VIS_EMB --> ES_V
    VLM --> PG
    VLM --> AGE
    VLM --> ES_T

    U --> QA
    QA --> ES_T
    QA --> ES_V
    QA --> AGE
    QA --> PG
    QA --> OBJ
    QA --> LLM
```

## 6. Main Flows

### 6.1 Ingestion: Dual Pipelines + VLM Enhancement
```mermaid
flowchart TD
    F["Raw File"]
    DU["Document Unit\npage / sheet / section / slide"]

    F --> DU

    subgraph VIS["Visual Chain (Full Coverage)"]
        R["Page-level Render"]
        PNG["Page PNG"]
        VP["Visual Pages"]
        GVE["Gemini Visual Embedding"]
        VV["Visual Vector"]
        VI["Visual Index"]

        DU --> R
        R --> PNG
        PNG --> VP
        VP --> GVE
        GVE --> VV
        VV --> VI
    end

    subgraph TXT["Text / Structured Chain"]
        P["Text / Table / Structure Parse"]
        SB["Semantic Blocks"]
        PC["Parent Chunks"]
        CC["Child Chunks"]
        OTE["OpenAI Text Embedding"]
        TV["Text Vector"]
        TI["Text Index"]

        DU --> P
        P --> SB
        SB --> PC
        PC --> CC
        CC --> OTE
        OTE --> TV
        TV --> TI
    end

    subgraph ENH["VLM Enhancement (On Demand)"]
        VLM2["VLM"]
        TP["Text Projection"]
        GF["Graph Facts"]
        RAW["Raw Payload Ref"]

        PNG --> VLM2
        VLM2 --> TP
        VLM2 --> GF
        VLM2 --> RAW

        TP --> TI
        GF --> AGE2["PostgreSQL + AGE"]
        RAW --> META["PostgreSQL / MinIO Meta"]
    end
```

### 6.2 Question -> Three-Way Retrieval -> Answer
```mermaid
flowchart TD
    Q["User Query"]
    QU["Query Understanding"]

    OQ["OpenAI Query Embedding"]
    GQ["Gemini Query Embedding"]

    TR["Text Retrieval\n(Text Index + BM25 + Entity)"]
    VR["Visual Retrieval\n(Visual Index)"]
    GR["Graph Retrieval\n(PostgreSQL + AGE)"]

    FU["Fusion / Rerank"]
    DC["Dynamic Context Selection"]
    CR["Critic"]
    LLM2["LLM Answer"]
    EV["Answer + Evidence"]

    Q --> QU

    QU --> OQ
    QU --> GQ
    QU --> GR

    OQ --> TR
    GQ --> VR

    TR --> FU
    VR --> FU
    GR --> FU

    FU --> DC
    DC --> CR
    CR --> LLM2
    LLM2 --> EV
```

### 6.3 LangGraph QA Orchestration
The default Q&A path is orchestrated with LangGraph using this pipeline:

```text
Planner -> Retriever -> Reasoner -> Critic -> Answer
```

```mermaid
flowchart LR
    U["User Question"] --> P["Planner\nIntent + Retrieval Plan"]
    P --> R["Retriever\nhybrid/relation/visual retrieval"]
    R --> RS["Reasoner\nEvidence summarization"]
    RS --> C["Critic\nEvidence quality check"]
    C -->|PASS| A["Answer\nLLM generation + citations"]
    C -->|EVIDENCE_EMPTY / ANCHOR_MISMATCH / EVIDENCE_WEAK| N["Safe Response\nno-evidence"]
    A --> O["Response to User"]
    N --> O
```

- Planner:
  Detects intent and decides retrieval plan (`top_k`, relation on/off).
- Retriever:
  Executes existing hybrid/relation/visual-fallback retrieval logic.
- Reasoner:
  Summarizes top evidence before final answer generation.
- Critic:
  Validates evidence quality and can block unsafe/weak answers.
- Answer:
  Generates final answer when passed; otherwise returns safe no-evidence response.

Current Critic reason codes:
- `EVIDENCE_EMPTY`: no evidence found
- `ANCHOR_MISMATCH`: query anchors do not match retrieved evidence
- `EVIDENCE_WEAK`: evidence exists but confidence is too low
- `PASS`: answer can proceed

### 6.4 Dynamic Context Selection
The LLM does not always receive every evidence type. Context is selected by intent:

- `fact_query -> text_only`
- `layout_query -> text_plus_image`
- `flow_query -> graph_plus_text`
- `explicit image request / visual-heavy -> graph_plus_text_plus_image`

### 6.5 User-visible Stage Status (WebSocket)
During Q&A execution, the frontend shows Japanese stage messages:

- `質問の意図を分析しています...`
- `根拠を検索しています...`
- `根拠を整理しています...`
- `回答の妥当性を確認しています...`
- `回答を生成しています...`

If Critic blocks the answer, the UI also shows `reason_code` and reason text.

## 7. Key APIs
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/upload/chunk`
- `POST /api/v1/upload/merge`
- `GET /api/v1/search/hybrid`
- `WS /api/v1/chat?token=...`

## 8. Operational Notes
- Replace all secrets in `.env` before production use
- Default setup is single-node oriented
- Tune ES/Kafka/OpenAI/Gemini/AGE parameters per data volume and latency targets
- Copy `.env.example` to `.env` before first run

### 8.1 Key Environment Variables

#### Text / Chat
- `OPENAI_API_KEY`
- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_CHAT_MODEL`

#### Visual Embedding
- `GEMINI_VISUAL_EMBEDDING_ENABLED`
- `GEMINI_VISUAL_EMBEDDING_BACKEND=ai_studio|vertex|auto`
- `GEMINI_VISUAL_EMBEDDING_MODEL`
- `GEMINI_VISUAL_EMBEDDING_DIMENSIONS`
- `GEMINI_API_KEY`

#### Graph
- `GRAPH_BACKEND=postgres_relational|postgres_age`
- `POSTGRES_AGE_ENABLED=true|false`
- `POSTGRES_AGE_GRAPH_NAME=knowledge_graph`

## 9. Extra Documents
- Japanese user guide: [README_ja.md](./README_ja.md)
- Architecture notes: [docs/architecture_ja.md](./docs/architecture_ja.md)
- Graph notes: [docs/graph_store_zh.md](./docs/graph_store_zh.md)
- Security policy: [SECURITY.md](./SECURITY.md)
- Contributing guide: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Release notes: [RELEASE_NOTES.md](./RELEASE_NOTES.md)
