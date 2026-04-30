# SCIP Indexer 安裝與建索引指引

不論 `index.scip` 是否已存在，每次代碼變更後應重新建索引以確保分析結果與當前代碼一致。

## scip-extractor 本體 CLI 安裝

```bash
which scip-extract scip-graph-merge scip-graph-query || {
  git clone https://github.com/NeoJay0705/scip-extractor.git
  pip install -e ./scip-extractor
}
```

> 若已 clone 過，直接 `pip install -e <path>` 即可。CLI 提供 `scip-extract`、`scip-graph-merge`、`scip-graph-query` 三個入口。

## Python

```bash
# 檢查是否已安裝，未安裝則安裝
which scip-python || npm install -g @sourcegraph/scip-python

# 啟動 virtualenv（必須，scip-python 需從 virtualenv 解析 import）
source .venv/bin/activate

# 建立索引（--project-name 會成為 SCIP package name，影響 --output-modules 與 --project-modules 的匹配粒度）
scip-python index . --project-name=MY_PROJECT
```
> 需要 Node v16+ 與 Python 3.10+。若遇 OOM，設定 `NODE_OPTIONS="--max-old-space-size=8192"`。

## Go

```bash
# 檢查是否已安裝，未安裝則安裝
which scip-go || go install github.com/sourcegraph/scip-go/cmd/scip-go@latest

# 在專案根目錄（含 go.mod）執行：
scip-go
```

## TypeScript / JavaScript

```bash
# 檢查是否已安裝，未安裝則安裝
which scip-typescript || npm install -g @sourcegraph/scip-typescript

npm install  # 確保 node_modules 存在
# TypeScript（需 tsconfig.json）：
scip-typescript index
# JavaScript（無 tsconfig.json）：
scip-typescript index --infer-tsconfig
```

> 所有 indexer 預設輸出 `index.scip` 至當前目錄。
