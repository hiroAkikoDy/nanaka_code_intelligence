# Task.md — Issue #7
### タスク名：増分インデックス実装
作成日：2026-06-03
SPEC.md参照：Issue #7
セキュリティ分類：A
Worktree：worktree-issue-7
依存：なし（Issue #8・#10と並列実行可）

---

## Objective（目的）

`scripts/ingest_code_graph.py` に `update_incrementally()` 関数を追加し、
`git diff` で変更ファイルだけを検出して再インデックスできる状態にする。
毎回全体を再インデックスする既存の `ingest_project()` の代替として機能する。

---

## Output format（出力形式）

| ファイル | 内容 |
|---|---|
| `scripts/ingest_code_graph.py` | 既存ファイルに `update_incrementally()` を追加 |
| `tests/test_incremental_index.py` | 新規テストファイル |

### 戻り値仕様

```python
update_incrementally(
    project_root: str = ".",
    driver: Any = None,  # None の場合は環境変数から接続
) -> dict[str, Any]

# 正常時（変更ファイルあり）
{
  "updated_files": ["src/a.py", "src/b.py"],
  "skipped": [],
  "error": None
}

# 変更ファイルなし
{
  "updated_files": [],
  "skipped": [],
  "error": None
}

# Neo4j未起動時（クラッシュせずに返す）
{
  "updated_files": [],
  "skipped": [],
  "error": "Cannot connect to Neo4j. Run ingest_code_graph.py first."
}

# gitリポジトリ外
{
  "updated_files": [],
  "skipped": [],
  "error": "Not a git repository or git command failed."
}
```

---

## 実装指針

```python
# scripts/ingest_code_graph.py に追加する関数

def update_incrementally(
    project_root: str = ".",
    driver: Any = None,
) -> dict[str, Any]:
    # Step 1：git diffで変更されたPythonファイルを取得
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    if result.returncode != 0:
        return {"updated_files": [], "skipped": [],
                "error": "Not a git repository or git command failed."}

    changed_py = [
        f for f in result.stdout.splitlines()
        if f.endswith(".py")
    ]

    if not changed_py:
        return {"updated_files": [], "skipped": [], "error": None}

    # Step 2：ドライバー取得（引数優先、なければ環境変数から）
    # Step 3：各変更ファイルについて古いノードを削除してから再追加
    #   MATCH (f:File {path: $path}) DETACH DELETE f  ← 古いノードを削除
    #   続いて parse_python_file() → session.run() で再追加
    # Step 4：結果を返す
```

**既存関数の再利用方針：**
- `parse_python_file(fp: Path)` → そのまま使う
- `create_neo4j_driver(uri, user, password)` → driver=None時に使う
- Neo4jのMERGEクエリ → ingest_project()のものを参考に個別ファイル単位で実行

---

## Tool guidance（使用するもの）

- **使うもの：** `subprocess`（git diff）・既存 `ingest_code_graph.py` の関数群・`neo4j>=5.0.0`・`pathlib`
- **使わないもの：** GitPython・外部API・ChromaDB・sentence-transformers（Issue #8の範囲）

---

## Task boundary（境界）

`update_incrementally()` 関数の追加まで。
ベクトルインデックスへの対応はIssue #8で行う（この関数には含めない）。

---

## TDD手順（必ず守ること）

```
Redフェーズ：
1. tests/test_incremental_index.py に失敗するテストを書く
   テストケース（最低3件）：
   a. 変更Pythonファイルがある場合 → updated_filesに含まれる
   b. 変更Pythonファイルがない場合 → {"updated_files": [], "skipped": [], "error": None}
   c. Neo4j未起動時 → "error"キーにメッセージを返す（クラッシュしない）
   d. gitリポジトリ外 → "error"キーにメッセージを返す
2. pytest を実行して FAILED を確認する（スキップ禁止）

Greenフェーズ：
3. update_incrementally() を実装する
4. pytest tests/test_incremental_index.py が全件 PASSED になるまで修正する

手動テストフェーズ：
5. python -c で動作確認
   python -c "from scripts.ingest_code_graph import update_incrementally; print(update_incrementally('.'))"
6. 既存53件が引き続き通ることを確認
   pytest --tb=short（全件通過が必要）
```

---

## 完了条件

- `pytest tests/test_incremental_index.py` 全件 PASSED
- `pytest` 全体（53件＋新規）全件 PASSED
- `update_incrementally()` に型アノテーション（`dict[str, Any]`）付き
- Work_Report.md の車検項目が全て ○

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：増分インデックス実装
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件：○ / ✗
├── pytest（全体・新規テスト含む）：全__件通過 ○ / ✗
├── セキュリティ（分類A確認）：○ / ✗
└── 型アノテーション（dict[str, Any]）：○ / ✗

## セキュリティ確認
├── 外部APIへの意図しない送信：なし / あり
├── ハードコードされたシークレット：なし / あり
└── 入力値のバリデーション：実装済み / 未実装

問題・逸脱：
次タスクへの申し送り：（Issue #9 Hybrid RAG統合へ）
  - git diffのコマンド仕様（HEAD~1 or --cached 等）を変更した場合は記載
  - Neo4j接続の取得方法を変更した場合は記載
```
