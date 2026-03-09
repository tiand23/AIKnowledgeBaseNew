# AI Knowledge Base Platform

This document is the user-focused guide for international readers.  
For architecture/deep design review, see [docs/architecture_ja.md](./docs/architecture_ja.md).

## 1. What You Can Do
- Upload documents in chunks and process them asynchronously
- Parse image-heavy documents with VLM-assisted structuring
- Ask questions with hybrid retrieval (vector + full-text)
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
flowchart TD
    U["User (Web UI)"] --> A["FastAPI API Gateway<br/>/api/v1/*"]
    U --> W["WebSocket Chat<br/>/api/v1/chat"]

    A --> AUTH["Auth/JWT"]
    A --> UP["Upload API<br/>chunk/status/merge"]
    A --> S["Search API<br/>/search/hybrid"]

    UP --> DB[(PostgreSQL<br/>file_upload/chunk_info)]
    UP --> R[(Redis<br/>upload bitmap/progress)]
    UP --> M[(MinIO<br/>raw file/chunks/images)]
    UP --> K[[Kafka<br/>document_parse]]

    K --> P["Document Processor"]
    P --> M
    P --> O["OpenAI Vision/Embedding"]
    P --> ES[(Elasticsearch<br/>text + dense_vector)]
    P --> DB

    W --> C["Chat Service"]
    C --> S
    C --> O2["OpenAI Chat"]
    C --> DB
    C --> R
    S --> ES
    S --> ACL["Permission Service<br/>owner/public/org/default"]
```

## 6. Main Flows

### 6.1 Upload -> Parse -> Index
```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as FastAPI /upload
    participant Redis as Redis
    participant SQL as PostgreSQL
    participant MinIO as MinIO
    participant Kafka as Kafka
    participant Proc as Document Processor
    participant ES as Elasticsearch
    participant OpenAI as OpenAI

    UI->>API: POST /upload/chunk (chunk_i)
    API->>MinIO: save temp/{md5}/{idx}
    API->>Redis: SETBIT upload:chunks:{md5}
    API->>SQL: upsert chunk_info / file_upload(status=0)

    UI->>API: POST /upload/merge
    API->>MinIO: compose temp/* -> documents/{user}/{file}
    API->>SQL: file_upload.status=1 (MERGED)
    API->>Kafka: publish document_parse(file_md5,...)

    Kafka->>Proc: consume message
    Proc->>SQL: status=2 (PROCESSING)
    Proc->>MinIO: download merged file
    Proc->>OpenAI: vision/embedding (if needed)
    Proc->>ES: index text/vector chunks
    Proc->>SQL: write vectors/sources + status=3 (DONE)
```

### 6.2 Question -> Retrieve -> Answer
```mermaid
sequenceDiagram
    participant UI as Web UI
    participant WS as WebSocket /chat
    participant Chat as Chat Service
    participant Planner as Planner
    participant Search as Search Service
    participant Reasoner as Reasoner
    participant Critic as Critic
    participant ACL as Permission Service
    participant ES as Elasticsearch
    participant OpenAI as OpenAI Chat
    participant DB as PostgreSQL/Redis

    UI->>WS: question
    WS->>Chat: message
    Chat-->>UI: status(planner)
    Chat->>Planner: intent routing / query understanding
    Planner-->>Chat: retrieval plan(top_k, relation)
    Chat-->>UI: status(retriever)
    Chat->>Search: retrieval(plan, query, user_ctx)
    Search->>ACL: build permission filter
    Search->>ES: vector + text retrieval
    ES-->>Search: top-k evidence
    Search-->>Chat: ranked chunks + sources
    Chat-->>UI: status(reasoner)
    Chat->>Reasoner: evidence summarization
    Reasoner-->>Chat: reasoning notes
    Chat-->>UI: status(critic)
    Chat->>Critic: evidence check
    Critic-->>Chat: PASS / reason_code
    alt PASS
        Chat-->>UI: status(answer)
        Chat->>OpenAI: prompt + evidence context
        OpenAI-->>Chat: answer
    else FAIL
        Chat-->>UI: no-evidence + reason_code
    end
    Chat->>DB: usage/conversation logging
    Chat-->>UI: answer + evidence links/images
```

### 6.3 LangGraph QA Orchestration (New)
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

### 6.4 User-visible Stage Status (WebSocket)
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
- Tune ES/Kafka/OpenAI parameters per data volume and latency targets
- Copy `.env.example` to `.env` before first run

## 9. Extra Documents
- Japanese user guide: [README_ja.md](./README_ja.md)
- Architecture notes: [docs/architecture_ja.md](./docs/architecture_ja.md)
- Security policy: [SECURITY.md](./SECURITY.md)
- Contributing guide: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Release notes: [RELEASE_NOTES.md](./RELEASE_NOTES.md)
