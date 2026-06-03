# nanaka-code-intelligence

Claude Code と Kilo Code に「このファイルの影響範囲を調べて」と自然言語で質問できる MCP サーバー群。

コード解析の中核機能（影響範囲分析・シンボル参照・型チェック・グラフベース呼び出し追跡）を独立したインフラとして公開しています。`.mcp.json` を追加するだけで、nanaka-farm・nanaka-aivtuber・任意の Python プロジェクトから再利用できます。

---

## アーキテクチャ

3 段階の実装により、環境に応じて段階的に機能を利用できます。

```
┌─────────────────────────────────────────────────────┐
│ Phase 1: ast版（標準ライブラリのみ・常時利用可）        │
│   code_intelligence_server.py                        │
│   get_file_structure / find_references               │
│   get_impact_analysis                                │
├─────────────────────────────────────────────────────┤
│ Phase 2: LSP版（pyright連携・pyright未導入でも起動可）  │
│   lsp_server.py                                      │
│   check_types / get_diagnostics                      │
├─────────────────────────────────────────────────────┤
│ Phase 3: Neo4j版（グラフDB・Neo4j未起動でも起動可）     │
│   code_graph_server.py                               │
│   get_impact_analysis_graph / get_call_graph         │
└─────────────────────────────────────────────────────┘
```

各サーバーは **グレースフルデグラデーション** を採用しています。外部依存（pyright・Neo4j）が利用できない場合でもサーバー自体は起動し、呼び出し時に分かりやすいエラーメッセージを返します。

---

## セットアップ手順

### 1. リポジトリをクローン

```bash
git clone https://github.com/hiroAkikoDy/nanaka-code-intelligence.git
cd nanaka-code-intelligence
```

### 2. 依存パッケージをインストール

```bash
pip install -r requirements.txt --break-system-packages
```

### 3. .mcp.json を作成

```bash
cp .mcp.json.example .mcp.json
```

`.mcp.json` 内の `/path/to/nanaka-code-intelligence` を実際のパスに変更してください。

### 4. Neo4j版を使う場合（オプション）

環境変数を設定します。

```bash
export NEO4J_PASSWORD=your_password
```

### 5. コードをNeo4jに取り込む（オプション）

```bash
python scripts/ingest_code_graph.py \
  --project-root /path/to/your-project \
  --neo4j-pass $NEO4J_PASSWORD
```

---

## 使い方

### ast版（標準ライブラリのみ・常時利用可）

#### `get_file_structure`

ファイルの関数・クラス・import一覧を取得します。

```python
# 呼び出し例（Claude Code / Kilo Code から）
get_file_structure(file_path="src/main.py")
```

```json
{
  "file": "src/main.py",
  "imports": ["os", "sys"],
  "classes": ["MyClass"],
  "functions": ["main", "helper"],
  "error": null
}
```

#### `find_references`

プロジェクト内のシンボル参照箇所を検索します。

```python
find_references(symbol_name="my_func", project_root="/path/to/project")
```

```json
{
  "symbol": "my_func",
  "references": [
    {"file": "src/other.py", "line": 42, "content": "result = my_func(x)"}
  ],
  "count": 1,
  "error": null
}
```

#### `get_impact_analysis`

ファイル変更時の影響ファイルを特定します。

```python
get_impact_analysis(file_path="src/main.py", project_root="/path/to/project")
```

```json
{
  "changed_file": "src/main.py",
  "defines": ["main", "helper", "MyClass"],
  "impacted_files": [
    {"file": "src/other.py", "references": ["helper"]}
  ],
  "count": 1,
  "error": null
}
```

---

### LSP版（pyrightが必要）

#### `check_types`

指定ファイルの型エラーをチェックします。pyright未インストール時はエラーメッセージを返します（クラッシュしません）。

```python
check_types(file_path="src/main.py")
```

```json
{
  "file": "src/main.py",
  "errors": 2,
  "warnings": 0,
  "passed": false,
  "details": [
    {"line": 10, "message": "Type error ...", "severity": "error"}
  ]
}
```

#### `get_diagnostics`

プロジェクト全体の型エラーを集計します。

```python
get_diagnostics(project_root="/path/to/project")
```

```json
{
  "project_root": "/path/to/project",
  "total_errors": 5,
  "total_warnings": 2,
  "files_with_errors": [
    {"file": "src/main.py", "errors": 3}
  ],
  "passed": false
}
```

---

### Neo4j版（Neo4j起動・ingest済みが必要）

#### `get_impact_analysis_graph`

グラフDBを使った高精度な影響範囲分析です。CALLS リレーションを辿り、関数の呼び出し元を跨いだ影響を検出できます。

```python
get_impact_analysis_graph(file_path="src/main.py")
```

```json
{
  "changed_file": "src/main.py",
  "defines": ["main", "helper"],
  "impacted_files": [
    {"file": "src/other.py", "via_symbols": ["helper"]}
  ],
  "count": 1,
  "source": "neo4j"
}
```

#### `get_call_graph`

関数の呼び出し関係を指定した深さまで辿ります。

```python
get_call_graph(function_name="main", depth=2)
```

```json
{
  "function": "main",
  "depth": 2,
  "calls": [
    {"from": "main", "to": "helper", "depth": 1},
    {"from": "helper", "to": "util", "depth": 2}
  ],
  "count": 2,
  "source": "neo4j",
  "note": "Callee nodes may be merged across files if names are identical."
}
```

---

## テスト実行

```bash
pytest
```

全サーバーのテストが実行されます（Neo4j・pyrightなしでもモックテストが通ります）。

---

## 設計説明

### ゴール設計（KAOS）

SPEC.md に定義された KAOS ゴールツリーに基づき、3 段階の実装を計画しました。

```
G0: Claude CodeとKilo Codeがコードの影響範囲を正確に把握できる
├── G1: ast版MCPサーバーが動作する（Phase 1）
├── G2: LSP版MCPサーバーが動作する（Phase 2）
└── G3: Neo4j版MCPサーバーが動作する（Phase 3）

Avoid: Neo4j未起動時にMCPサーバーがクラッシュする
Avoid: pyright未インストール時に起動できない
```

### なぜ ast → LSP → Neo4j の3段階か

| 段階 | 依存 | 精度 | 利用条件 |
|---|---|---|---|
| ast版 | なし（標準ライブラリのみ） | テキストマッチ | 常時利用可 |
| LSP版 | pyright | 型レベル | `npm install -g pyright` |
| Neo4j版 | Neo4j Desktop | グラフトラバーサル | Neo4j起動 + ingest済み |

ast版はテキスト検索のため同名の別シンボルも拾いますが、セットアップ不要でどこでも動きます。Neo4j版は関数の呼び出し関係をグラフとして格納するため、間接的な影響まで追跡できます。段階的に導入することで、プロジェクトの規模に応じた最適な精度を選べます。

### グレースフルデグラデーション

各サーバーは外部依存の有無に関わらず起動します。

- **pyright未インストール時**: `check_types` / `get_diagnostics` は `"error"` キーにガイドメッセージを返す
- **Neo4j未起動時**: `get_impact_analysis_graph` / `get_call_graph` は `"source": "error"` と接続エラーメッセージを返す
- ast版は常に動作するため、最低限の影響分析はどの環境でも利用可能

### MCP サーバーの通信方式

全サーバーは stdio 方式を採用しています。Claude Code / Kilo Code の `.mcp.json` に追記するだけで利用開始でき、追加のネットワークポートは不要です。

### フォルダ構造

```
nanaka-code-intelligence/
├── SPEC.md
├── README.md
├── requirements.txt
├── .gitignore
├── .mcp.json.example
├── mcp_servers/
│   ├── __init__.py
│   ├── code_intelligence_server.py    # ast版（Phase 1）
│   ├── lsp_server.py                  # LSP版（Phase 2）
│   └── code_graph_server.py           # Neo4j版（Phase 3）
├── scripts/
│   └── ingest_code_graph.py           # Neo4j取込スクリプト
└── tests/
    ├── __init__.py
    ├── test_code_intelligence.py
    ├── test_lsp_server.py
    ├── test_code_graph_server.py
    └── test_ingest_code_graph.py
```

---

## ライセンス

MIT
