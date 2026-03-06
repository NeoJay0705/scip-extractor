# SCIP Deep Context Extractor

從 [SCIP](https://sourcegraph.com/docs/code-search/code-navigation/scip) 索引中提取深層上下文的 CLI 工具。透過解析 SCIP 索引檔（`index.scip`），追蹤函式呼叫關係並輸出結構化的程式碼上下文，適用於程式碼理解、測試影響分析等場景。

## 安裝

### 1. 建立虛擬環境

```bash
cd /home/neojhou/repos/scip-extractor
python3 -m venv .venv
```

### 2. 啟動虛擬環境

```bash
source .venv/bin/activate
```

### 3. 安裝專案（Editable Mode）

使用 editable install，讓 `git pull` 後程式碼變更自動生效，無需重新安裝：

```bash
pip install -e .
```

如需開發或測試用的額外套件：

```bash
pip install -e ".[dev]"    # 包含 pytest
pip install -e ".[test]"   # 包含 pytest + jsonschema
```

### 4. 驗證安裝

```bash
scip-extract --version
scip-extract --help
```

## 使用方式

安裝後會有三個 CLI 指令可用：

- **`scip-extract`** — 從 SCIP 索引提取深層上下文（Markdown / Call Graph JSON）
- **`scip-graph-merge`** — 合併多個 Graph JSON
- **`scip-graph-query`** — 查詢呼叫關係、測試影響分析

各指令的完整參數說明、使用情境與範例，請參閱 **[使用者文件（USER_DOC.md）](docs/USER_DOC.md)**。

## 前置作業：建立 SCIP 索引

使用此工具前，需先為目標專案建立 SCIP 索引。完成後會在專案根目錄產生 `index.scip` 檔案。

### Python 專案

- **環境要求**：Python 3.x + npm
- **安裝 indexer**：`npm install -g @sourcegraph/scip-python`
- **建立索引**：`npx @sourcegraph/scip-python index .`（在專案根目錄執行）

### Go 專案

- **環境要求**：Go 1.17+
- **安裝 indexer**：`go install github.com/sourcegraph/scip-go/cmd/scip-go@latest`
- **建立索引**：`scip-go`（在含 `go.mod` 的目錄執行）

### TypeScript 專案

- **環境要求**：Node.js 18+ / TypeScript 5+
- **安裝 indexer**：`npm install -g @sourcegraph/scip-typescript`
- **建立索引**：`npx scip-typescript index`（在含 `tsconfig.json` 的目錄執行）

## 專案結構

```
scip-extractor/
├── pyproject.toml          # 專案設定與依賴
├── src/
│   └── scip_deep_context/  # 主要程式碼
│       ├── cli.py           # CLI 進入點
│       ├── scip_loader.py   # SCIP 索引載入
│       ├── bfs_traverser.py # BFS 呼叫圖遍歷
│       ├── graph_merger.py  # Graph 合併
│       ├── graph_query.py   # Graph 查詢
│       └── ...
└── docs/                   # 文件
```
