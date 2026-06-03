# Task.md — Issue #4
### タスク名：Neo4jコードグラフ取込スクリプト実装
作成日：2026-06-03
SPEC.md参照：Issue #4
セキュリティ分類：A
Worktree：worktree-issue-4

---

## Objective（目的）

Pythonプロジェクトのコードをastで解析してNeo4jに取り込む
`ingest_code_graph.py` を実装し、
nanaka-aivtuber（または任意のPythonプロジェクト）のコードが
Neo4jグラフDBに格納される状態にする。

---

## Output format（出力形式）

| ファイル | 役割 |
|---|---|
| `scripts/ingest_code_graph.py` | 取込スクリプト本体 |

### Neo4jノード・リレーション設計

```
ノード：
(:File {path: str, name: str})
(:Function {name: str, file: str, line: int})
(:Class {name: str, file: str, line: int})
(:Import {name: str, file: str})

リレーション：
(:File)-[:DEFINES]->(:Function)
(:File)-[:DEFINES]->(:Class)
(:File)-[:IMPORTS]->(:Import)
(:Function)-[:CALLS]->(:Function)  # 呼び出し関係
```

### 実行インターフェース

```bash
# 基本使用
python scripts/ingest_code_graph.py --project-root /path/to/project

# オプション
--neo4j-uri   bolt://localhost:7687  (デフォルト)
--neo4j-user  neo4j                  (デフォルト)
--neo4j-pass  password               (必須・環境変数 NEO4J_PASSWORD でも可)
--clear       既存グラフを削除してから取り込む

# 実行結果の出力例
Ingested 42 files, 156 functions, 23 classes into Neo4j.
```

---

## Tool guidance（使用するもの）

- **使うもの：** Python `ast`（標準）・`neo4j>=5.0.0`・`argparse`・`pathlib`
- **使わないもの：** MCP SDK・tree-sitter・pyright・requests・外部API
- **Neo4j接続：** `bolt://localhost:7687`（デフォルト）
- **認証情報：** 環境変数 `NEO4J_PASSWORD` から読む（ハードコード禁止）

---

## Task boundary（境界）

Pythonファイルの解析とNeo4jへの格納まで。
MCPサーバーとしての公開（Issue #5）は含まない。

---

## 重要：グレースフルデグラデーション要件

Neo4j未起動時は：
- 接続エラーを分かりやすいメッセージで表示して終了する
- スタックトレースをそのまま出さない

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_ingest_code_graph.py に失敗するテストを書く
   - astパース結果の検証（Neo4jなしで単体テスト可能な部分）
   - 存在しないプロジェクトルートのエラー処理
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. scripts/ingest_code_graph.py を実装する
4. pytest が全件 PASSED になるまで修正する

手動テストフェーズ：
5. 実際に nanaka-aivtuber のパスを渡して取込実行
   python scripts/ingest_code_graph.py \
     --project-root /path/to/nanaka-aivtuber \
     --neo4j-pass <password>
6. Neo4j Browser で以下クエリを実行して確認：
   MATCH (n) RETURN count(n)
   MATCH (f:File) RETURN f.name LIMIT 10
```

---

## 完了条件

- `pytest tests/test_ingest_code_graph.py` が全件 PASSED
- 実際のPythonプロジェクトが Neo4j に格納される
- `MATCH (n) RETURN count(n)` がノード数を返す
- 全関数に型アノテーションがついている
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：Neo4jコードグラフ取込スクリプト実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest：全__件通過 ○ / ✗
├── セキュリティ（分類A確認・NEO4J_PASSWORD環境変数確認）：○ / ✗
└── 型アノテーション：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり（パスワードは環境変数のみ）
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Issue #5 code_graph_server.py へ）
  - Neo4jのノード・リレーション設計を変更した場合は必ず記載
```
