# AI Knowledge Base Platform

日本企業向けナレッジベース基盤のOSS実装です。  
このREADMEは「利用者向けガイド」として、セットアップと利用フローを最短で理解できる構成にしています。

## 1. できること
- ドキュメントを分割アップロードして非同期解析
- すべての文書を page-level visual asset として扱う視覚検索基盤
- テキスト/表/構造解析による text-first RAG
- Gemini 画像ベクトル + OpenAI テキストベクトルの二重検索
- VLM による text projection / graph facts の生成
- PostgreSQL + Apache AGE による graph 検索
- 組織タグベースのアクセス制御（owner/public/org/default）
- 評価データを蓄積し、品質改善に活用

## 2. 想定ユースケース
- 設計書・運用手順書・画面遷移図の横断検索
- 組織別に公開範囲を制御した社内ナレッジ共有
- 回答品質（再現率/適合率/忠実性/完全性）の継続改善

## 3. クイックスタート（Docker）
1. 設定ファイルを作成
```bash
cp .env.example .env
```
2. `.env` を編集（最低限 `OPENAI_API_KEY` と各種パスワードを設定）
3. 起動
```bash
cd app
./start_docker.sh pg up
```
4. 動作確認
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl http://localhost:8000/health
```
5. 停止
```bash
cd app
./start_docker.sh pg down
```

## 4. 最小操作フロー
1. アカウント登録（所属組織/主組織を設定）
2. ドキュメントをアップロード（公開範囲・組織タグを指定）
3. ナレッジQ&Aで質問
4. 根拠リンク/画像付き回答を確認

## 5. システム概要
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

## 6. 主要フロー

### 6.1 文書入庫: 二重チェーン + VLM 増強
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

### 6.2 質問 -> 三路召回 -> 回答
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

### 6.3 LangGraph問答オーケストレーション
本プロジェクトの通常Q&Aパスは、LangGraphで次の5段を実行します。

```text
Planner -> Retriever -> Reasoner -> Critic -> Answer
```

```mermaid
flowchart LR
    U["ユーザー質問"] --> P["Planner\n意図判定・検索計画"]
    P --> R["Retriever\nhybrid/relation/visual 検索"]
    R --> RS["Reasoner\n根拠要点整理"]
    RS --> C["Critic\n根拠妥当性チェック"]
    C -->|PASS| A["Answer\nLLM回答生成 + 引用付与"]
    C -->|EVIDENCE_EMPTY / ANCHOR_MISMATCH / EVIDENCE_WEAK| N["安全応答\nno-evidence"]
    A --> O["回答返却"]
    N --> O
```

- Planner:
  質問意図を判定し、`top_k` や relation検索の有無を決定
- Retriever:
  既存の hybrid/relation/visual fallback ロジックで根拠を取得
- Reasoner:
  上位根拠を要約し、回答生成前の整理ノートを作成
- Critic:
  根拠妥当性を判定し、必要なら回答を保留
- Answer:
  通過時は回答生成へ、失敗時は安全な no-evidence 応答へ

Critic の判定コード（現行）:
- `EVIDENCE_EMPTY`: 根拠0件
- `ANCHOR_MISMATCH`: 質問対象語と根拠が不一致
- `EVIDENCE_WEAK`: 根拠はあるが信頼度が低い
- `PASS`: 回答可能

### 6.4 Dynamic Context Selection
質問タイプに応じて、LLM に渡す証拠形式を切り替えます。

- `fact_query -> text_only`
- `layout_query -> text_plus_image`
- `flow_query -> graph_plus_text`
- `明示的な画像要求 / visual-heavy -> graph_plus_text_plus_image`

これにより、すべての回答で画像を無条件投入せず、コストとノイズを抑えています。

### 6.5 ユーザー可視ステータス（WebSocket）
Q&A実行中は、フロント側に段階ステータスを日本語で表示します。

- `質問の意図を分析しています...`
- `根拠を検索しています...`
- `根拠を整理しています...`
- `回答の妥当性を確認しています...`
- `回答を生成しています...`

Criticで保留になった場合は、`reason_code` と理由文を表示します（例: `EVIDENCE_WEAK`）。

## 7. 代表API
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/upload/chunk`
- `POST /api/v1/upload/merge`
- `GET /api/v1/search/hybrid`
- `WS /api/v1/chat?token=...`

## 8. 設定と運用上の注意
- 本番では `.env` の秘密情報（JWT/DB/SMTP/OpenAI/Gemini）を必ず差し替えてください
- 初期設定は単一ノード想定です（HA構成は別途設計が必要）
- 外部サービス（ES/Kafka/OpenAI/Gemini/AGE）のパラメータは実データに合わせて調整してください
- 初回は `.env.example` を `.env` にコピーしてから利用してください

### 8.1 主要環境変数

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

## 9. 既知の制約（v0.1.0-draft）
- 単一ノード構成を前提（高可用構成は未提供）
- 大規模負荷向けの自動スケールは未実装
- 一部機能は運用チューニング（ES/Kafka/OpenAI）前提

## 10. 追加ドキュメント
- 英語版ユーザーガイド: [README_en.md](./README_en.md)
- 設計思想・アーキテクチャ詳細: [docs/architecture_ja.md](./docs/architecture_ja.md)
- Graph 設計メモ: [docs/graph_store_zh.md](./docs/graph_store_zh.md)
- セキュリティポリシー: [SECURITY.md](./SECURITY.md)
- コントリビュート: [CONTRIBUTING.md](./CONTRIBUTING.md)
- リリースノート: [RELEASE_NOTES.md](./RELEASE_NOTES.md)

## 11. セキュリティと報告窓口
脆弱性報告手順は [SECURITY.md](./SECURITY.md) を参照してください。

## 12. コントリビュート
開発手順・PRルールは [CONTRIBUTING.md](./CONTRIBUTING.md) を参照してください。

## 13. リリースノート
初期版ノートは [RELEASE_NOTES.md](./RELEASE_NOTES.md) を参照してください。

## 14. ライセンス
ライセンスは `LICENSE` を参照してください（公開時に選定）。
