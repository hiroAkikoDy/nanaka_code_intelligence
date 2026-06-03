# Task.md — Issue #10
### タスク名：git_historyツール実装
作成日：2026-06-03
セキュリティ分類：A
Worktree：worktree-issue-10
依存：なし（Issue #7・#8・#9と並列実行可）

---

## Objective（目的）

`get_file_history` MCPツールを `mcp_servers/code_intelligence_server.py` に追加し、
「このファイルはいつ・どのコミットで変更されたか」を
Claude Code / Kilo Code から呼び出せる状態にする。

**設計方針（決定済み）：**
PROV-O全体実装は過剰設計と判断した。
`git log` をジャストインタイムで呼ぶ1ツールで十分。
Neo4jへの来歴格納はスコープ外。

---

## Output format（出力形式）

| ファイル | 内容 |
|---|---|
| `mcp_servers/code_intelligence_server.py` | `get_file_history` ツール追加（既存ファイルを修正） |
| `tests/test_git_history.py` | 新規テストファイル |

### 戻り値仕様

```python
# get_file_history(file_path: str, max_commits: int = 10) -> list[dict[str, Any]]

# 正常時
[
  {
    "hash": "a1b2c3d4",       # 短縮ハッシュ8文字
    "date": "2026-06-03 10:00:00 +0900",
    "message": "feat: add incremental index"
  },
  ...
]

# コミット履歴がない（新規ファイル等）
[]

# gitリポジトリ外 or ファイルが見つからない
[{"error": "Not a git repository or file not found."}]
```

---

## 実装指針

```python
# mcp_servers/code_intelligence_server.py に追加

import subprocess

@mcp.tool()
def get_file_history(
    file_path: str,
    max_commits: int = 10,
) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "git", "log",
            f"--max-count={max_commits}",
            "--follow",
            "--format=%H|%ai|%s",
            "--",
            file_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return [{"error": "Not a git repository or file not found."}]

    commits: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({
                "hash": parts[0][:8],
                "date": parts[1],
                "message": parts[2],
            })

    return commits
```

**注意：**
- `subprocess` が既に `code_intelligence_server.py` にimportされているか確認すること
- されていない場合は追加すること
- `mcp` デコレータのツール名は `tool_get_file_history` でなく `get_file_history` とすること
  （Issue #2の `tool_` プレフィックス慣習に合わせる場合は一貫性を優先すること）

---

## Tool guidance（使用するもの）

- **使うもの：** `subprocess`（git log）・`mcp>=1.0.0`
- **使わないもの：** GitPython・Neo4j・PROV-O・外部API・sentence-transformers

---

## Task boundary（境界）

`get_file_history` ツールの追加まで。
Neo4jへの来歴格納・PROV-O実装はスコープ外（設計決定済み）。

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_git_history.py に失敗するテストを書く
   テストケース（最低3件）：
   a. 正常時 → list[dict] を返す（subprocess.runをモック）
   b. gitリポジトリ外 → [{"error": "..."}] を返す
   c. 履歴がないファイル → [] を返す
   d. max_commits パラメータが git log コマンドに正しく渡される
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. get_file_history() を実装する
4. pytest tests/test_git_history.py が全件 PASSED になるまで修正する

手動テストフェーズ：
5. 実際のファイルで動作確認
   python -c "
   from mcp_servers.code_intelligence_server import get_file_history
   import json
   print(json.dumps(get_file_history('scripts/ingest_code_graph.py'), indent=2))
   "
6. gitリポジトリ外での動作確認（エラーメッセージが返ること）
7. 既存53件が引き続き通ることを確認
   pytest --tb=short
```

---

## 完了条件

- `pytest tests/test_git_history.py` 全件 PASSED
- `pytest` 全体（53件＋新規）全件 PASSED
- `get_file_history` に型アノテーション（`list[dict[str, Any]]`）付き
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：git_historyツール実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest（全体）：全__件通過 ○ / ✗
├── セキュリティ（分類A確認）：○ / ✗
└── 型アノテーション（list[dict[str, Any]]）：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Issue #9 Hybrid RAGへ）
  - code_intelligence_server.pyに追加したimport文を記載
  - ツール名の命名規則（tool_プレフィックスの有無）を記載
```
