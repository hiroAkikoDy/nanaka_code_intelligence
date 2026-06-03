# Task.md — Issue #2
### タスク名：ast版MCPサーバー実装
作成日：2026-06-03
SPEC.md参照：Issue #2
セキュリティ分類：A
Worktree：worktree-issue-2

---

## Objective（目的）

`get_file_structure`・`find_references`・`get_impact_analysis` の3ツールを持つ
MCP サーバーを実装し、pytest全件通過・型アノテーション付きの状態にする。

---

## Output format（出力形式）

| ファイル | 役割 |
|---|---|
| `mcp_servers/code_intelligence_server.py` | MCPサーバー本体 |
| `tests/test_code_intelligence.py` | pytestテスト |

戻り値はすべて `dict` 型（型アノテーション必須）。

### 各ツールの戻り値仕様

```python
# get_file_structure(file_path: str) -> dict
{
  "file": "path/to/file.py",
  "imports": ["os", "sys"],
  "classes": ["MyClass"],
  "functions": ["my_func"],
  "error": None  # エラー時のみ文字列
}

# find_references(symbol_name: str, project_root: str) -> dict
{
  "symbol": "my_func",
  "references": [
    {"file": "path/to/file.py", "line": 42, "content": "result = my_func(x)"}
  ],
  "count": 1
}

# get_impact_analysis(file_path: str, project_root: str) -> dict
{
  "changed_file": "path/to/file.py",
  "defines": ["my_func", "MyClass"],
  "impacted_files": [
    {"file": "path/to/other.py", "references": ["my_func"]}
  ],
  "count": 1
}
```

---

## Tool guidance（使用するもの）

- **使うもの：** Python `ast`（標準ライブラリ）・`mcp>=1.0.0`
- **使わないもの：** tree-sitter・外部API・Neo4j・pyright・requests

---

## Task boundary（境界）

ast版3ツールの実装・テストまで。
LSP（check_types）・Neo4j（ingest_code_graph）は含まない。

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_code_intelligence.py に失敗するテストを書く
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. mcp_servers/code_intelligence_server.py を実装する
4. pytest が全件 PASSED になるまで修正する

手動テストフェーズ（python -c で確認）：
5. 存在しないファイルパスを渡した場合
6. 空のPythonファイルを渡した場合
7. 構文エラーのあるPythonファイルを渡した場合
8. 問題があれば pytest に追加してから修正する
```

---

## 完了条件

- `pytest tests/test_code_intelligence.py` が全件 PASSED
- 上記エッジケース3件を `python -c` で確認済み
- 全関数に型アノテーションがついている
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：ast版MCPサーバー実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest：全__件通過 ○ / ✗
├── セキュリティ（分類A確認）：○ / ✗
└── 型アノテーション：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：
```
