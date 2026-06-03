# Task.md — Issue #9
### タスク名：Hybrid RAG統合
作成日：2026-06-03
セキュリティ分類：A
Worktree：worktree-issue-9
依存：Issue #7・#8完了済み（pytest 77件通過確認済み）

---

## Objective（目的）

`hybrid_search` MCPツールを実装し、
コードグラフ検索（構造的理解）とベクトル検索（意味的理解）を
Reciprocal Rank Fusion（RRF）で統合した
Hybrid RAGをClaude Code / Kilo Codeから呼び出せる状態にする。

---

## Output format（出力形式）

| ファイル | 内容 |
|---|---|
| `mcp_servers/code_intelligence_server.py` | `hybrid_search` ツール追加（既存ファイルを修正） |
| `tests/test_hybrid_search.py` | 新規テストファイル |

### 戻り値仕様

```python
# hybrid_search(query: str, project_root: str = ".", top_k: int = 5) -> dict[str, Any]
{
  "query": "generate_daily_script",
  "graph_results": [
    {"file": "src/scheduler.py", "references": ["generate_daily_script"]}
  ],
  "vector_results": [
    {"function": "generate_weekly_script", "file": "src/scheduler.py", "score": 0.91}
  ],
  "hybrid_results": [
    {"file": "src/scheduler.py", "rrf_score": 0.032}
  ],
  "note": "hybrid_resultsはRRF統合済み・最も信頼性が高い"
}

# Neo4j未起動 or sentence-transformers未インストール時（部分的に動作）
{
  "query": "generate_daily_script",
  "graph_results": [...],   # ast版は常に動作
  "vector_results": [],     # Neo4j不可時は空
  "hybrid_results": [...],  # graph_resultsのみでRRF
  "note": "vector_search unavailable: Cannot connect to Neo4j..."
}
```

---

## 使用する既存関数（#7・#8の申し送り反映）

| 関数 | 場所 | 役割 |
|---|---|---|
| `find_references()` | `code_intelligence_server.py` | グラフ検索のベース（ast版） |
| `get_impact_analysis()` | `code_intelligence_server.py` | 影響ファイル取得 |
| `find_similar_code()` | `code_intelligence_server.py` | ベクトル検索（Issue #8実装済み） |
| `_get_neo4j_driver()` | `code_intelligence_server.py` | Neo4j接続（Issue #8実装済み） |

**重要：** `find_similar_code()` はすでに `code_intelligence_server.py` に実装済み。
直接呼び出すこと（reimplementしない）。

---

## 実装指針

```python
# mcp_servers/code_intelligence_server.py に追加

def _graph_search(query: str, project_root: str) -> list[dict[str, Any]]:
    # find_references を使ってシンボル検索
    refs = find_references(query, project_root)
    return refs.get("references", [])


def _vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
    # find_similar_code を使う（Neo4j不可時は[]を返す）
    result = find_similar_code(query, top_k=top_k)
    if result and "error" in result[0]:
        return []
    return result


def _reciprocal_rank_fusion(
    graph: list[dict[str, Any]],
    vector: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion（RRF）
    score = Σ 1 / (k + rank + 1)
    """
    scores: dict[str, float] = {}

    for rank, item in enumerate(graph):
        key = item.get("file", item.get("name", ""))
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)

    for rank, item in enumerate(vector):
        key = item.get("file", "")
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)

    return [
        {"file": f, "rrf_score": round(v, 6)}
        for f, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ][:5]


@mcp.tool()
def tool_hybrid_search(
    query: str,
    project_root: str = ".",
    top_k: int = 5,
) -> dict[str, Any]:
    graph_results = _graph_search(query, project_root)
    vector_results = _vector_search(query, top_k)
    hybrid_results = _reciprocal_rank_fusion(graph_results, vector_results)

    note = "hybrid_resultsはRRF統合済み・最も信頼性が高い"
    if not vector_results:
        note = f"vector_search unavailable: Neo4j未起動またはインデックス未作成。graph_resultsのみでRRF。"

    return {
        "query": query,
        "graph_results": graph_results,
        "vector_results": vector_results,
        "hybrid_results": hybrid_results,
        "note": note,
    }
```

---

## Tool guidance（使用するもの）

- **使うもの：** 既存の `find_references()`・`find_similar_code()`・`_get_neo4j_driver()`（すべて同ファイル内）
- **使わないもの：** LangChain等の外部RAGフレームワーク・ChromaDB・requests・外部API

---

## Task boundary（境界）

`hybrid_search`（内部では `tool_hybrid_search`）ツールの追加まで。
ファイル監視による自動更新はスコープ外。

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_hybrid_search.py に失敗するテストを書く
   テストケース（最低4件）：
   a. graph_results・vector_results・hybrid_resultsの3キーが返る
   b. hybrid_resultsがRRFでスコアリングされている（高いほど上位）
   c. Neo4j不可時でもgraph_resultsだけで動く（vector_results=[]）
   d. RRFのscoreが 1/(k+rank+1) の式で計算されている

2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. tool_hybrid_search() を実装する
4. pytest tests/test_hybrid_search.py が全件 PASSED になるまで修正する

手動テストフェーズ：
5. pytest --tb=short で全件通過を確認（77件＋新規）
```

---

## 完了条件

- `pytest tests/test_hybrid_search.py` 全件 PASSED
- `pytest` 全体（77件＋新規）全件 PASSED
- `tool_hybrid_search` に型アノテーション（`dict[str, Any]`）付き
- Neo4j不可時でもグレースフルに動作する
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：Hybrid RAG統合
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest（全体）：全__件通過 ○ / ✗
├── セキュリティ（外部APIへの送信なし）：○ / ✗
└── 型アノテーション（dict[str, Any]）：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Phase 2 完了）
```
