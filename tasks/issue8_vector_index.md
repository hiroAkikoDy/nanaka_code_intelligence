# Task.md — Issue #8
### タスク名：Neo4jベクトルインデックス実装
作成日：2026-06-03
セキュリティ分類：A
Worktree：worktree-issue-8
依存：なし（Issue #7・#10と並列実行可）

---

## Objective（目的）

`sentence-transformers` でコードをembeddingして
Neo4jのネイティブベクトルインデックスに格納し、
`find_similar_code` MCPツールで意味的に似たコードを検索できる状態にする。

ChromaDBは使わない（Neo4j 5.11以降のネイティブベクトルサポートで一本化）。

---

## Output format（出力形式）

| ファイル | 内容 |
|---|---|
| `scripts/setup_vector_index.py` | Neo4jベクトルインデックス初期化スクリプト（新規） |
| `scripts/ingest_code_graph.py` | embeddingプロパティ追加（既存ファイルを修正） |
| `mcp_servers/code_intelligence_server.py` | `find_similar_code` ツール追加（既存ファイルを修正） |
| `tests/test_vector_search.py` | 新規テストファイル |

### 戻り値仕様

```python
# find_similar_code(query: str, top_k: int = 5) -> list[dict[str, Any]]
# 正常時
[
  {"function": "classify_comment", "file": "src/classifier.py", "score": 0.92},
  {"function": "detect_sentiment", "file": "src/analyzer.py", "score": 0.87},
]

# Neo4j未起動 or インデックス未作成時
[{"error": "Cannot connect to Neo4j or vector index not found. Run setup_vector_index.py first."}]
```

---

## 実装指針

### 1. scripts/setup_vector_index.py（新規）

```python
# Neo4jにベクトルインデックスを作成する
# 初回のみ実行が必要

def create_vector_index(driver: Any) -> None:
    with driver.session() as session:
        session.run("""
            CREATE VECTOR INDEX code_embeddings
            IF NOT EXISTS
            FOR (f:Function)
            ON f.embedding
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 384,
                    `vector.similarity_function`: 'cosine'
                }
            }
        """)
    print("Vector index 'code_embeddings' created (or already exists).")
```

### 2. scripts/ingest_code_graph.py の修正

`ingest_project()` でFunctionノードを作成するとき、
`embedding` プロパティを追加する。

```python
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer('all-MiniLM-L6-v2')

# ingest_project()内のFunctionノード作成部分に追加：
embedding = _model.encode(f"{func['name']} {func.get('calls', [])}").tolist()
session.run(
    """
    MERGE (fn:Function {name: $name, file: $file, line: $line})
    SET fn.embedding = $embedding
    ...
    """,
    embedding=embedding,
    ...
)
```

### 3. mcp_servers/code_intelligence_server.py への追加

```python
from sentence_transformers import SentenceTransformer
_embed_model = SentenceTransformer('all-MiniLM-L6-v2')

@mcp.tool()
def find_similar_code(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    driver = _get_neo4j_driver()  # 既存の接続ロジックを使う
    if driver is None:
        return [{"error": "Cannot connect to Neo4j or vector index not found..."}]

    query_embedding = _embed_model.encode(query).tolist()
    with driver.session() as session:
        result = session.run(
            """
            CALL db.index.vector.queryNodes(
                'code_embeddings', $top_k, $embedding
            )
            YIELD node, score
            RETURN node.name AS function, node.file AS file, score
            ORDER BY score DESC
            """,
            top_k=top_k,
            embedding=query_embedding,
        )
        return [dict(r) for r in result]
```

**注意：** `code_intelligence_server.py` には現状Neo4j接続がない。
Neo4j接続ロジックを追加する必要がある（`code_graph_server.py` の `_get_driver()` を参考にすること）。
ただし `code_graph_server.py` を直接importするのではなく、
`code_intelligence_server.py` 内に同様の接続ロジックを独立して実装すること。

---

## requirements.txt への追加

```
sentence-transformers>=2.0.0
```

---

## Tool guidance（使用するもの）

- **使うもの：** `sentence-transformers`（`pip install sentence-transformers`）・`neo4j>=5.0.0`・`mcp>=1.0.0`
- **使わないもの：** ChromaDB・Pinecone・OpenAI Embedding API・外部ベクトルDB

---

## Task boundary（境界）

`find_similar_code` ツールの追加まで。
Hybrid RAGの統合（RRF）はIssue #9で行う。

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_vector_search.py に失敗するテストを書く
   テストケース（最低3件）：
   a. find_similar_codeが list[dict] を返す（SentenceTransformerをモック）
   b. Neo4j未起動時 → errorキーを持つリストを返す（クラッシュしない）
   c. top_k パラメータが正しくCypherに渡される
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. setup_vector_index.py・ingest_code_graph.py修正・
   code_intelligence_server.py修正を実装する
4. pytest tests/test_vector_search.py が全件 PASSED になるまで修正する

手動テストフェーズ（Neo4j起動中に実行）：
5. python scripts/setup_vector_index.py でインデックス作成
6. python scripts/ingest_code_graph.py --project-root . --neo4j-pass $NEO4J_PASSWORD
   でembedding付きでingest
7. python -c "..." で find_similar_code を呼んで類似関数が返ることを確認
8. 既存53件が引き続き通ることを確認
   pytest --tb=short
```

---

## 完了条件

- `pytest tests/test_vector_search.py` 全件 PASSED
- `pytest` 全体（53件＋新規）全件 PASSED
- `find_similar_code` に型アノテーション（`list[dict[str, Any]]`）付き
- `requirements.txt` に `sentence-transformers>=2.0.0` が追加されている
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：Neo4jベクトルインデックス実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest（全体）：全__件通過 ○ / ✗
├── セキュリティ（外部APIへの送信なし確認）：○ / ✗
└── 型アノテーション：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
│   （sentence-transformersはローカル実行・外部送信なし）
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Issue #9 Hybrid RAG統合へ）
  - embeddingの次元数・モデル名を変更した場合は必ず記載
  - Neo4jベクトルインデックス名（デフォルト: code_embeddings）を変更した場合は記載
  - code_intelligence_server.pyに追加したNeo4j接続ロジックの関数名を記載
```
