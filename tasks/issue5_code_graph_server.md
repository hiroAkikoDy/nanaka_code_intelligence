# Task.md — Issue #5
### タスク名：Neo4j版MCPサーバー実装（グラフ影響範囲分析）
作成日：2026-06-03
SPEC.md参照：Issue #5
セキュリティ分類：A
Worktree：worktree-issue-5
依存：Issue #4（ingest_code_graph.py）完了済み

---

## Objective（目的）

`get_impact_analysis_graph`・`get_call_graph` の2ツールを持つ
Neo4j版MCPサーバーを実装し、pytest全件通過（Neo4jモック）の状態にする。
ast版より高精度な影響範囲分析をNeo4jのグラフクエリで実現する。

---

## Output format（出力形式）

| ファイル | 役割 |
|---|---|
| `mcp_servers/code_graph_server.py` | MCPサーバー本体 |
| `tests/test_code_graph_server.py` | pytestテスト（Neo4jモック） |

戻り値はすべて `dict[str, Any]` 型（型アノテーション必須）。

### 各ツールの戻り値仕様

```python
# get_impact_analysis_graph(file_path: str) -> dict[str, Any]
# Neo4j起動中の場合
{
  "changed_file": "path/to/file.py",
  "defines": ["my_func", "MyClass"],
  "impacted_files": [
    {"file": "path/to/other.py", "via_symbols": ["my_func"]}
  ],
  "count": 1,
  "source": "neo4j"   # "neo4j" or "error"
}

# Neo4j未起動の場合（クラッシュせずに返す）
{
  "changed_file": "path/to/file.py",
  "defines": [],
  "impacted_files": [],
  "count": 0,
  "source": "error",
  "error": "Cannot connect to Neo4j. Run ingest_code_graph.py first."
}

# get_call_graph(function_name: str, depth: int = 2) -> dict[str, Any]
# Neo4j起動中の場合
{
  "function": "my_func",
  "depth": 2,
  "calls": [
    {"from": "my_func", "to": "helper", "depth": 1},
    {"from": "helper", "to": "util", "depth": 2}
  ],
  "count": 2,
  "source": "neo4j"
}
```

---

## Tool guidance（使用するもの）

- **使うもの：** `neo4j>=5.0.0`・`mcp>=1.0.0`・`os.environ.get`
- **使わないもの：** Python `ast`・pyright・requests・外部API
- **再利用するもの：** `scripts/ingest_code_graph.py` の `create_neo4j_driver` 関数
  - import方法：`from scripts.ingest_code_graph import create_neo4j_driver`
- **Neo4j接続情報：** 環境変数から取得すること
  ```
  NEO4J_URI      デフォルト: bolt://localhost:7687
  NEO4J_USER     デフォルト: neo4j
  NEO4J_PASSWORD 必須（ハードコード禁止）
  ```

---

## Task boundary（境界）

2ツール（get_impact_analysis_graph / get_call_graph）の実装・テストまで。
ingest処理（Issue #4）・ast版（Issue #2）は含まない。
README・ドキュメント（Issue #6）は含まない。

---

## 重要：Issue #4からの申し送り事項（必ず守ること）

1. **`_ValidateAction` クラスは使わないこと**
   - `scripts/ingest_code_graph.py` に未使用のデッドコードとして存在する
   - `create_neo4j_driver` のみを import して使う

2. **`:CALLS` リレーションのcalleeは `name` のみ（`file`なし）**
   - 同名関数が複数ファイルに存在すると1ノードに統合されている
   - `get_call_graph` の結果にはこの制約を `"note"` キーで明記すること
   ```python
   "note": "Callee nodes may be merged across files if names are identical."
   ```

3. **Neo4jスキーマ（Issue #4が構築済み）**
   ```cypher
   (:File {path, name})
   (:Function {name, file, line})
   (:Class {name, file, line})
   (:Import {name, file})
   (:File)-[:DEFINES]->(:Function)
   (:File)-[:DEFINES]->(:Class)
   (:File)-[:IMPORTS]->(:Import)
   (:Function)-[:CALLS]->(:Function)
   ```

---

## グレースフルデグラデーション要件

Neo4j未起動・接続失敗時は：
- **サーバーが起動できること**（クラッシュ禁止）
- 各ツールを呼んだ時に `"source": "error"` と `"error"` キーを返すこと
- pytestでこの動作を必ずテストすること

---

## Cypherクエリ設計（参考）

```cypher
-- get_impact_analysis_graph: file_pathが定義するシンボルを参照するファイルを取得
MATCH (f:File {path: $file_path})-[:DEFINES]->(sym)
WHERE sym:Function OR sym:Class
WITH sym
MATCH (other:File)-[:DEFINES]->(caller:Function)-[:CALLS]->(sym)
WHERE other.path <> $file_path
RETURN other.path AS file, collect(sym.name) AS via_symbols

-- get_call_graph: 関数の呼び出し関係をN段まで辿る
MATCH path = (fn:Function {name: $function_name})-[:CALLS*1..$depth]->(callee)
RETURN path
```

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_code_graph_server.py に失敗するテストを書く
   - Neo4j正常応答のケース（Driverをモック）
   - Neo4j未起動のケース（接続失敗をモック）
   - get_call_graph の depth パラメータ検証
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. mcp_servers/code_graph_server.py を実装する
4. pytest が全件 PASSED になるまで修正する

手動テストフェーズ（Neo4j起動中に実行）：
5. python -c でget_impact_analysis_graphを呼ぶ
6. Neo4j Browser で結果を目視確認
   MATCH (f:File)-[:DEFINES]->(fn:Function)-[:CALLS]->(callee)
   RETURN f.name, fn.name, callee.name LIMIT 20
```

---

## 完了条件

- `pytest tests/test_code_graph_server.py` が全件 PASSED（Neo4jモック）
- Neo4j未起動時の動作確認済み（グレースフルデグラデーション）
- 全関数に型アノテーションがついている（`dict[str, Any]` まで明記）
- `mcp: FastMCP` に型アノテーション付き（Issue #3の軽微な指摘を反映）
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：Neo4j版MCPサーバー実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest：全__件通過 ○ / ✗
├── セキュリティ（NEO4J_PASSWORD環境変数確認）：○ / ✗
└── 型アノテーション（dict[str, Any]まで）：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Issue #6 README・ドキュメントへ）
  - .mcp.json.exampleに追加が必要なMCPサーバー設定を記載すること
```
