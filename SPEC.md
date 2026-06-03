# SPEC.md — nanaka-code-intelligence
# バージョン：1.0
# 作成日：2026-06-03
# セキュリティ分類：A（コード構造は公開情報）

---

## 1. プロジェクト概要

### 目的

Claude CodeとKilo Codeが「このファイルの影響範囲を調べて」と自然言語で質問できる
MCPサーバーを作る。

コード解析の中核機能（影響範囲分析・シンボル参照・型チェック）を
独立したインフラとして公開し、nanaka-farm・nanaka-aivtuber・将来の全プロジェクトから
`.mcp.json`を追加するだけで再利用できる状態にする。

### 成功状態

```
「generate_daily_script.pyの影響範囲を調べて」
とClaude Codeに頼んだら
MCPサーバーが影響ファイルの一覧を返してくる
```

### 背景・なぜ作るか

弘晃さんが農場・研究・ピアノを並走させながらコードを書く環境において、
「今触ったファイルが何に影響するか」を瞬時に把握できないと
回帰バグの発見が遅れる。
LLMに聞く前に影響範囲が自動で分かれば、Task.mdの「完了条件」も
精度高く書ける。

### 参考資料

- Neo4j公式ブログ：Codebase Knowledge Graph
  https://neo4j.com/blog/developer/codebase-knowledge-graph/
- ArXiv：Tree-sitter → AST → Neo4j パターン
  https://arxiv.org/html/2510.04905v1
- Anthropic公式：MCP設計（LSPのメッセージフローを参考）
  https://www.anthropic.com/news/building-effective-agents

---

## 2. ペルソナ定義

### Claude Code（指揮者）

- Task.mdを作成し、Kilo Codeに委任する
- Work_Report.mdで品質を車検する
- このMCPサーバーを呼んで影響範囲を把握し、精度の高いTask.mdを書く

### Kilo Code（ソリスト）

- Claude CodeのTask.mdを受け取り実装する
- このMCPサーバーのfind_references・check_typesを使い
  実装前に参照箇所を把握してから変更する

### 古閑 弘晃（承認者）

- SPEC.md・Task.mdを承認する
- 農場との並走があるため、承認待ち時間を最小化する設計を好む
- Zenn記事化を想定しているため、説明コメントを丁寧に入れること

---

## 3. ユースケース

### UC1：影響範囲分析

```
アクター：Claude Code
事前条件：プロジェクトがNeo4jに取り込み済み
基本フロー：
  1. get_impact_analysis(file_path) を呼ぶ
  2. 変更されたファイルが定義する関数・クラスを取得
  3. それらを参照するファイルをNeo4jから検索
  4. 影響ファイルの一覧を返す
例外フロー：
  2a. Neo4j未起動 → ast版で代替してエラーを通知
  2b. ファイルが存在しない → エラーメッセージを返す
```

### UC2：シンボル参照検索

```
アクター：Kilo Code
基本フロー：
  1. find_references(symbol_name, project_root) を呼ぶ
  2. プロジェクト内の全Pythonファイルを検索
  3. シンボル名が含まれる行を返す
```

### UC3：ファイル構造取得

```
アクター：Claude Code / Kilo Code
基本フロー：
  1. get_file_structure(file_path) を呼ぶ
  2. astでファイルを解析
  3. 関数・クラス・importの一覧を返す
```

### UC4：型チェック

```
アクター：Kilo Code（Work_Report.md の車検として）
基本フロー：
  1. check_types(file_path) を呼ぶ
  2. pyright --outputjson でエラーを取得
  3. {"errors": N, "passed": bool} を返す
例外フロー：
  2a. pyright未インストール → エラーメッセージを返す（起動は継続）
```

---

## 4. KAOSゴール

```
G0: Achieve[Claude CodeとKilo Codeが
    コードの影響範囲を正確に把握できる]
├── G1: Achieve[ast版MCPサーバーが動作する]
│   ├── G1.1: Achieve[get_file_structureが動作する]
│   ├── G1.2: Achieve[find_referencesが動作する]
│   └── G1.3: Achieve[get_impact_analysisが動作する]
├── G2: Achieve[LSP版MCPサーバーが動作する]
│   ├── G2.1: Achieve[check_typesが動作する]
│   └── G2.2: Achieve[get_diagnosticsが動作する]
└── G3: Achieve[Neo4j版MCPサーバーが動作する]
    ├── G3.1: Achieve[ingest_code_graphが動作する]
    └── G3.2: Achieve[get_impact_analysis_graphが動作する]

Avoid[Neo4j未起動時にMCPサーバーがクラッシュする]
Avoid[pyright未インストール時に起動できない]
Assumption[Python 3.10以上がインストール済み]
Assumption[Neo4j Desktop 5.x がインストール済み]
```

---

## 5. NFR（非機能要件）

| 項目 | 要件 |
|---|---|
| セキュリティ | 分類A（コード構造を外部送信しても問題なし） |
| 応答時間 | 各ツール呼び出し3秒以内 |
| 保守性 | astからTree-sitterへの移行が容易な設計 |
| 可用性 | Neo4j未起動・pyright未インストール時も利用可能な機能は動き続けること |
| 再利用性 | .mcp.jsonの追加だけで全プロジェクトから使えること |

---

## 6. Alloy完了条件

```alloy
assert AstServerOK {
  全ツールが3秒以内にレスポンスを返す
}

assert GracefulDegradation {
  neo4j_down implies ast_server_still_works
}

assert TDDCompliant {
  全実装にテストが先行して存在する
}
```

---

## 7. GitHub Issue計画（Worktree割り当て付き）

### Issue #1：プロジェクト基盤

```
Worktree：main
内容：フォルダ構造・設定ファイル・requirements.txt
依存：なし
完了条件：GitHub上で構造が確認できる
```

### Issue #2：code_intelligence_server.py

```
Worktree：worktree-issue-2
内容：get_file_structure / find_references / get_impact_analysis
依存：Issue #1完了後
完了条件：pytest全件通過・型アノテーション付き
```

### Issue #3：lsp_server.py

```
Worktree：worktree-issue-3
内容：check_types / get_diagnostics
依存：Issue #1完了後（Issue #2と並列可）
完了条件：pytest全件通過・pyright未インストール時動作確認
```

### Issue #4：ingest_code_graph.py

```
Worktree：worktree-issue-4
内容：PythonファイルをNeo4jに取り込むスクリプト
依存：Issue #1完了後（Issue #2・#3と並列可）
完了条件：nanaka-aivtuberのコードがNeo4jに格納される
```

### Issue #5：code_graph_server.py

```
Worktree：worktree-issue-5
内容：get_impact_analysis_graph / get_call_graph
依存：Issue #4完了後
完了条件：pytest全件通過（Neo4jモック）
```

### Issue #6：README・ドキュメント

```
Worktree：main
内容：セットアップ手順・使い方・設計説明
依存：Issue #2〜5完了後
```

---

## 8. フォルダ構造

```
nanaka-code-intelligence/
├── SPEC.md
├── README.md
├── requirements.txt
├── .gitignore
├── .mcp.json.example
├── mcp_servers/
│   ├── __init__.py
│   ├── code_intelligence_server.py    # Issue #2
│   ├── lsp_server.py                  # Issue #3
│   └── code_graph_server.py           # Issue #5
├── scripts/
│   └── ingest_code_graph.py           # Issue #4
└── tests/
    ├── __init__.py
    ├── test_code_intelligence.py
    ├── test_lsp_server.py
    └── test_code_graph_server.py
```

---

## 9. 実装ロードマップ

```
Phase 1（今）：SPEC.md作成・承認
Phase 2：Issue #1 → フォルダ構造・GitHub push
Phase 3：Issue #2・#3・#4（並列） → ast版・LSP版・Neo4j取込
Phase 4：Issue #5（#4依存） → グラフ版
Phase 5：Issue #6 → README・Zenn記事化
```
