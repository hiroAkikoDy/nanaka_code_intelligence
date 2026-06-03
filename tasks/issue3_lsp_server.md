# Task.md — Issue #3
### タスク名：LSP版MCPサーバー実装（pyright連携）
作成日：2026-06-03
SPEC.md参照：Issue #3
セキュリティ分類：A
Worktree：worktree-issue-3

---

## Objective（目的）

`check_types`・`get_diagnostics` の2ツールを持つMCPサーバーを実装し、
pytest全件通過・**pyright未インストール時でも起動できる**状態にする。

---

## Output format（出力形式）

| ファイル | 役割 |
|---|---|
| `mcp_servers/lsp_server.py` | MCPサーバー本体 |
| `tests/test_lsp_server.py` | pytestテスト |

戻り値はすべて `dict` 型（型アノテーション必須）。

### 各ツールの戻り値仕様

```python
# check_types(file_path: str) -> dict
# pyright がインストールされている場合
{
  "file": "path/to/file.py",
  "errors": 2,
  "warnings": 0,
  "passed": False,
  "details": [
    {"line": 10, "message": "Type error ...", "severity": "error"}
  ]
}

# pyright が未インストールの場合（クラッシュせずに返す）
{
  "file": "path/to/file.py",
  "errors": 0,
  "warnings": 0,
  "passed": False,
  "details": [],
  "error": "pyright is not installed. Run: npm install -g pyright"
}

# get_diagnostics(project_root: str) -> dict
{
  "project_root": "path/to/project",
  "total_errors": 5,
  "total_warnings": 2,
  "files_with_errors": [
    {"file": "path/to/file.py", "errors": 3}
  ],
  "passed": False
}
```

---

## Tool guidance（使用するもの）

- **使うもの：** `subprocess`（pyright呼び出し）・`mcp>=1.0.0`・`shutil.which`（pyright存在確認）
- **使わないもの：** Python `ast`・Neo4j・requests・外部API
- **pyrightコマンド：** `pyright --outputjson <file_path>`

---

## Task boundary（境界）

pyright連携の2ツール実装・テストまで。
ast版（get_file_structure等）・Neo4j版は含まない。

---

## 重要：グレースフルデグラデーション要件

pyright未インストール時は：
- **サーバーが起動できること**（クラッシュ禁止）
- `check_types` を呼んだ時に `"error"` キーにメッセージを返すこと
- pytest でこの動作を必ずテストすること（`shutil.which` をモックして確認）

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_lsp_server.py に失敗するテストを書く
   - pyright ありの場合（モック）
   - pyright なしの場合（shutil.which をモック）
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. mcp_servers/lsp_server.py を実装する
4. pytest が全件 PASSED になるまで修正する

手動テストフェーズ（python -c で確認）：
5. 存在しないファイルパスを渡した場合
6. pyright 未インストール環境のシミュレーション（PATH から除外）
7. 問題があれば pytest に追加してから修正する
```

---

## 完了条件

- `pytest tests/test_lsp_server.py` が全件 PASSED
- pyright未インストール時の動作確認済み（グレースフルデグラデーション）
- 全関数に型アノテーションがついている
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：LSP版MCPサーバー実装
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
