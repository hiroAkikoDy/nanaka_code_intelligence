# Task.md — Issue #6
### タスク名：README・セットアップドキュメント作成
作成日：2026-06-03
SPEC.md参照：Issue #6
セキュリティ分類：A
Worktree：main（直接コミット可）
依存：Issue #2〜#5 完了済み

---

## Objective（目的）

`README.md` と `.mcp.json.example` を完成させ、
このリポジトリをcloneした人が迷わずセットアップ・利用開始できる状態にする。
Zenn記事化を想定した丁寧な説明を含めること。

---

## Output format（出力形式）

| ファイル | 内容 |
|---|---|
| `README.md` | プロジェクト説明・セットアップ手順・使い方・設計説明 |
| `.mcp.json.example` | 3サーバー分の設定例（Issue #5のcode_graph_serverを追加） |

---

## README.md に含める内容（必須セクション）

### 1. プロジェクト概要（1〜2段落）

```
- 何を解決するか（「このファイルの影響範囲を調べて」をClaude Codeに頼める）
- 誰のためか（Claude Code・Kilo Codeユーザー）
- 再利用性（.mcp.jsonを追加するだけで全プロジェクトから使える）
```

### 2. アーキテクチャ図（テキストでもよい）

```
3段階の実装：
┌─────────────────────────────────────────┐
│ Phase 1: ast版（標準ライブラリのみ）       │
│   code_intelligence_server.py            │
│   get_file_structure / find_references   │
│   get_impact_analysis                   │
├─────────────────────────────────────────┤
│ Phase 2: LSP版（pyright連携）             │
│   lsp_server.py                          │
│   check_types / get_diagnostics          │
├─────────────────────────────────────────┤
│ Phase 3: Neo4j版（グラフDB）              │
│   code_graph_server.py                   │
│   get_impact_analysis_graph              │
│   get_call_graph                         │
└─────────────────────────────────────────┘
```

### 3. セットアップ手順

```bash
# (1) リポジトリをクローン
git clone https://github.com/hiroAkikoDy/nanaka_code_intelligence.git
cd nanaka_code_intelligence

# (2) 依存パッケージをインストール
pip install -r requirements.txt --break-system-packages

# (3) .mcp.json を作成（exampleをコピーしてパスを修正）
cp .mcp.json.example .mcp.json
# .mcp.json の /path/to/nanaka-code-intelligence を実際のパスに変更

# (4) Neo4j版を使う場合：環境変数を設定
export NEO4J_PASSWORD=your_password

# (5) コードをNeo4jに取り込む
python scripts/ingest_code_graph.py \
  --project-root /path/to/your-project \
  --neo4j-pass $NEO4J_PASSWORD
```

### 4. 使い方（各ツールの説明）

以下の各ツールについて「何ができるか」→「呼び出し例」→「戻り値例」の3点セットで記述：

```
ast版（標準ライブラリのみ・常時利用可）：
  - get_file_structure     : ファイルの関数・クラス・import一覧を取得
  - find_references        : プロジェクト内のシンボル参照箇所を検索
  - get_impact_analysis    : ファイル変更時の影響ファイルを特定

LSP版（pyrightが必要）：
  - check_types            : 指定ファイルの型エラーをチェック
  - get_diagnostics        : プロジェクト全体の型エラーを集計

Neo4j版（Neo4j起動・ingest済みが必要）：
  - get_impact_analysis_graph : グラフDBを使った高精度な影響範囲分析
  - get_call_graph            : 関数の呼び出し関係をN段まで可視化
```

### 5. テスト実行

```bash
pytest
```

### 6. 設計の説明（Zenn記事向け）

```
- KAOS/Alloyによるゴール設計の概要（SPEC.mdへのリンク）
- なぜast → LSP → Neo4jの3段階か（保守性・可用性のトレードオフ）
- グレースフルデグラデーションの設計方針
  （Neo4j未起動・pyright未インストール時でも使い続けられる）
- MCPサーバーのstdio方式について
```

---

## .mcp.json.example の更新内容

既存の3サーバー設定に加え、以下の環境変数設定を追記すること：

```json
{
  "mcpServers": {
    "code-intelligence": { ... },
    "lsp-server": { ... },
    "code-graph-server": {
      "command": "python",
      "args": [
        "/path/to/nanaka-code-intelligence/mcp_servers/code_graph_server.py"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password_here"
      },
      "description": "Neo4j版：グラフベースの影響範囲分析（Neo4j起動・ingest済みが必要）"
    }
  }
}
```

---

## Tool guidance（使用するもの）

- **使うもの：** Markdown記法・既存のSPEC.md・各サーバーの戻り値仕様
- **使わないもの：** Python実装・pytest・新しいライブラリ
- **参考にするもの：**
  - `mcp_servers/code_intelligence_server.py`（ツール仕様の確認）
  - `SPEC.md`（設計の説明に引用してよい）

---

## Task boundary（境界）

README.md と .mcp.json.example の完成まで。
コードの追加実装は含まない。

---

## 完了条件

- README.mdを読むだけでセットアップが完了できる
- 全7ツールの説明が記載されている
- .mcp.json.exampleにcode-graph-serverの設定が追加されている
- Zenn記事化を想定した設計説明セクションがある

---

## Work_Report.md テンプレート（完了時に出力）

```
### 完了報告：README・セットアップドキュメント作成
実施日：
完了条件の達成：○ / △ / ✗

## 車検結果
├── 完了条件（README読んでセットアップ完了できるか）：○ / ✗
├── 全7ツール記載：○ / ✗
├── .mcp.json.example更新：○ / ✗
└── Zenn記事向け設計説明：○ / ✗

問題・逸脱：
次タスクへの申し送り：（プロジェクト完了）
```
