# 使用者文件

## 前置作業

### 安裝 scip-deep-context

主要安裝方式（推薦）：

```bash
pipx install ./scip-deep-context
```

Fallback：系統無 pipx 時（替代方案）：

```bash
pip install --user ./scip-deep-context
```

開發者模式（需修改源碼時使用）：

```bash
pip install -e ./scip-deep-context
```

安裝完成後會有三個 CLI 指令可用：
- `scip-extract` — 從 SCIP 索引提取深層上下文
- `scip-graph-merge` — 合併多個 graph JSON
- `scip-graph-query` — 查詢 graph 中的呼叫關係

### 建立 SCIP 索引

#### Python

1. **環境要求**：Python 3.x 版本 + pip/npm
2. **安裝 SCIP indexer**：`npm install -g @sourcegraph/scip-python`
3. **建立索引**：`npx @sourcegraph/scip-python index .`（在專案根目錄執行）
4. **驗證**：確認 `index.scip` 檔案已生成且 file size > 0

#### Golang

1. **環境要求**：Go 1.17+
2. **安裝 SCIP indexer**：`go install github.com/sourcegraph/scip-go/cmd/scip-go@latest`
3. **建立索引**：`scip-go`（在含 `go.mod` 的目錄執行）
4. **驗證**：確認 `index.scip` 檔案已生成且 file size > 0

#### TypeScript

1. **環境要求**：Node.js 18+ / TypeScript 5+
2. **安裝 SCIP indexer**：`npm install -g @sourcegraph/scip-typescript`
3. **建立索引**：`npx scip-typescript index`（在含 `tsconfig.json` 的目錄執行）
4. **驗證**：確認 `index.scip` 檔案已生成且 file size > 0

> 💡 若需將 CLI 工具整合至 AI agent 工作流，請參閱 [Agent Skill 使用指引](./AGENT_SKILL.md)

---

# 所有情境

## 情境 1：提取函式的深層上下文（Markdown）

> 從指定進入點（檔案 + 行號）開始，BFS 展開呼叫圖，產出 Markdown 上下文。

**操作方式：** command line

**操作前置作業：** 完成安裝 scip-deep-context 與建立 SCIP 索引

**指令：**
```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file scripts/run_backtest.py \
  --entry-line 298 \
  --max-nodes 100000 \
  --exclude-patterns "local *" \
  --timeout 20 \
  > backtest_context.md
```

**參數說明：** 完整參數列表請見[附錄：完整 CLI 參數表](#附錄完整-cli-參數表)。

**預期結果：**
- stdout 輸出 Markdown 格式的深層上下文
- BFS 結果預設僅含 function/method/constructor 節點；parameter symbols（`method().(param)` 格式）及 field/property symbols 均排除（field 可透過 `--include-fields` 包含）
- exit code 0：成功
- exit code 1：有 broken links（仍產出結果）
- exit code 2：SCIP 載入或進入點定位失敗
- exit code 3：檔案路徑解析失敗

---

## 情境 2：提取函式的 Call Graph（JSON）

> 在提取 Markdown 上下文的同時，產出結構化的 call graph JSON，包含節點、邊、測試標記。

**操作方式：** command line

**操作前置作業：** 同情境 1

**指令：**
```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file scripts/run_backtest.py \
  --entry-line 298 \
  --max-nodes 100000 \
  --exclude-patterns "local *" \
  --timeout 20 \
  --graph-output backtest_graph.json \
  > backtest_context.md
```

**預期結果：**
- stdout 仍輸出 Markdown（與情境 1 相同）
- `backtest_graph.json` 寫入 call graph JSON（預設套用 containment dedup，可透過 `--no-dedup` 停用）

**Graph JSON 格式：**
```json
{
  "metadata": {
    "scip_index_hash": "sha256:abc123...",
    "entry_file": "scripts/run_backtest.py",
    "entry_line": 298,
    "entry_symbol": "main().",
    "context_file": null
  },
  "nodes": {
    "main().": {
      "file": "scripts/run_backtest.py",
      "lines": [290, 310],
      "layer": 0,
      "is_test": false,
      "is_partial": false
    },
    "BacktestEngine#run().": {
      "file": "quant_factory/backtest.py",
      "lines": [100, 150],
      "layer": 1,
      "is_test": false,
      "is_partial": false
    }
  },
  "edges": [
    { "from": "main().", "to": "BacktestEngine#run().", "type": "reference" }
  ]
}
```

**欄位說明：**

| 欄位 | 說明 |
|------|------|
| `metadata.scip_index_hash` | SCIP 索引檔的 SHA256 雜湊，用於合併時驗證來源一致性 |
| `metadata.entry_file` | 進入點檔案 |
| `metadata.entry_line` | 進入點行號 |
| `metadata.entry_symbol` | 進入點 symbol descriptor |
| `nodes` | key 為 function-like symbol descriptor（含 `()` 且非 parameter symbol），value 包含檔案位置、BFS 層級、是否為測試節點。parameter symbols（`method().(param)` 格式）及 field symbols 預設排除 |
| `nodes[].layer` | BFS 層級（0 = entry point） |
| `nodes[].is_test` | 是否為測試節點（依 SymbolRole.TEST 或檔案路徑 pattern 判定） |
| `nodes[].is_partial` | 是否為部分擷取（`true` 表示代碼範圍可能不完整，使用 indent detection 或 ±5 lines fallback）。預設值：`false` |
| `edges` | 呼叫邊列表，已去重並依 (from, to, type) 排序 |
| `edges[].type` | 邊類型，`"reference"`（呼叫引用）或 `"implementation"`（介面實作） |

**`is_partial` 過濾使用指引：**

若需取得「only-complete」子集（僅保留完整函式節點），可在消費層依 `is_partial` 過濾：

| 消費方式 | 做法 | 適用場景 |
|---------|------|---------|
| Markdown 輸出 | 搜尋 `*(partial extraction)*` 標記，跳過該區塊 | 人工閱讀 |
| Graph JSON 消費 | 過濾 `is_partial == false` 的節點 | 程式化消費 |
| 合併後 Graph | 同上，`is_partial` 已透過 OR 傳播（見情境 3 合併規則 #6） | 多來源合併 |

---

## 情境 3：合併多個 Graph JSON

> 從不同進入點分別提取 graph 後，合併成統一的 graph，用於全域查詢。

**操作方式：** command line

**操作前置作業：** 先用情境 2 產出多個 graph JSON

**指令：**
```bash
# 步驟 1：分別提取
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file scripts/run_backtest.py --entry-line 298 \
  --max-nodes 100000 --timeout 20 \
  --graph-output graph_backtest.json > /dev/null

scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file scripts/analyze.py --entry-line 50 \
  --max-nodes 100000 --timeout 20 \
  --graph-output graph_analyze.json > /dev/null

# 步驟 2：合併
scip-graph-merge graph_backtest.json graph_analyze.json -o unified_graph.json
```

**參數說明：**

| 參數 | 必要 | 說明 |
|------|:----:|------|
| `inputs` (positional) | ✅ | 一個或多個 graph JSON 檔案路徑 |
| `-o` / `--output` | ✅ | 輸出合併後的 JSON 路徑 |

**合併規則：**
1. **SCIP Hash 驗證**：所有輸入必須來自同一份 `index.scip`，否則報錯 `IndexHashMismatchError`
2. **節點聯集**：相同 key 的節點只保留一份，`is_test` 取 OR
3. **Layer 轉換**：單一 graph 的 `layer` 欄位轉為合併後的 `source_layers` dict，以 `context_file` 為 key
4. **邊去重**：相同 `(from, to, type)` 的邊只保留一份，最終依字母排序
5. **增量合併**：已合併的 graph 可再與其他 graph 合併
6. **`is_partial` 取 OR**：相同 key 的節點合併時，`is_partial` 取 OR（任一來源為 partial 則合併後為 partial）

**合併後 JSON 格式差異：**
```json
{
  "metadata": {
    "scip_index_hash": "sha256:abc123...",
    "sources": [
      { "entry_symbol": "main().", "context_file": null },
      { "entry_symbol": "analyze().", "context_file": null }
    ]
  },
  "nodes": {
    "main().": {
      "file": "scripts/run_backtest.py",
      "lines": [290, 310],
      "is_test": false,
      "is_partial": false,
      "source_layers": { "": 0 }
    }
  },
  "edges": [ ... ]
}
```
> 注意：合併後 `metadata` 中 `entry_file` / `entry_line` / `entry_symbol` 被 `sources` 陣列取代；節點的 `layer` 被 `source_layers` dict 取代。

**預期結果：**
- exit code 0：合併成功
- exit code 1：SCIP hash 不匹配
- exit code 2：其他錯誤（如檔案不存在）

---

## 情境 4：查詢 — 正向呼叫追蹤（Forward）

> 從指定節點出發，找出它直接或間接呼叫的所有函式。

**操作方式：** command line

**操作前置作業：** 透過情境 2 或情境 3 產出 graph JSON

**指令：**
```bash
scip-graph-query \
  --graph unified_graph.json \
  --forward-from 'main().' \
  --max-depth 3
```

**參數說明：**

| 參數 | 必要 | 說明 |
|------|:----:|------|
| `--graph` | ✅ | graph JSON 路徑（單一或合併後皆可） |
| `--max-depth` | | 最大追蹤深度（預設 10） |
| `--forward-from` | ✅* | Q1：正向查詢的起點 node key（支援 glob pattern 如 `*traverse*`） |
| `--reverse-from` | ✅* | Q2：反向查詢的起點 node key（支援 glob pattern） |
| `--test-impact` | ✅* | Q3：影響分析的目標 node key（支援 glob pattern） |
| `--coverage` | ✅* | Q4：覆蓋分析的測試 node key（支援 glob pattern） |
| `--list-nodes` | ✅* | 列出 graph 中所有 node key |

> *五種查詢模式互斥，必須指定其中一種。

**預期結果（stdout JSON）：**
```json
{
  "nodes": {
    "BacktestEngine#run().": {
      "file": "quant_factory/backtest.py",
      "lines": [100, 150],
      "is_test": false,
      "source_layers": { "": 0 }
    }
  },
  "is_truncated": false
}
```
- `nodes`：符合條件的節點（不含起點本身）
- `is_truncated`：`true` 表示 BFS 在 `max_depth` 處截斷，可能有更多節點
- 若 truncated，stderr 輸出警告訊息

---

## 情境 5：查詢 — 反向呼叫追蹤（Reverse）

> 找出哪些函式直接或間接呼叫了指定的目標函式。

**操作方式：** command line

**指令：**
```bash
scip-graph-query \
  --graph unified_graph.json \
  --reverse-from 'BacktestEngine#run().'
```

**預期結果：** 同情境 4 格式，列出所有呼叫者（callers）。

---

## 情境 6：查詢 — 測試影響分析（Test Impact）

> 找出哪些測試會受到指定函式修改的影響（反向追蹤 + 過濾出 `is_test=true` 的節點）。

**操作方式：** command line

**指令：**
```bash
scip-graph-query \
  --graph unified_graph.json \
  --test-impact 'BacktestEngine#run().'
```

**預期結果：** 同情境 4 格式，但 `nodes` 只包含 `is_test=true` 的測試節點。

**使用場景：** 修改了某個函式後，快速確認需要重新執行哪些測試。

---

## 情境 7：查詢 — 測試覆蓋分析（Coverage）

> 找出指定測試函式直接或間接測試了哪些 production 函式（正向追蹤 + 過濾出 `is_test=false` 的節點）。

**操作方式：** command line

**指令：**
```bash
scip-graph-query \
  --graph unified_graph.json \
  --coverage 'TestBacktest#test_run().'
```

**預期結果：** 同情境 4 格式，但 `nodes` 只包含 `is_test=false` 的 production 節點。

**使用場景：** 評估某個測試的覆蓋範圍，找出未被覆蓋的 production code。

---

## 情境 8：端到端工作流程

> 完整的典型使用流程：建立索引 → 多點提取 → 合併 → 查詢。

**操作方式：** command line

**指令：**
```bash
# 1. 建立 SCIP 索引
npx @sourcegraph/scip-python index .

# 2. 從多個進入點提取 graph
scip-extract \
  --scip-file index.scip --project-root . \
  --entry-file scripts/run_backtest.py --entry-line 298 \
  --max-nodes 100000 --timeout 20 \
  --graph-output graph_a.json > context_a.md

scip-extract \
  --scip-file index.scip --project-root . \
  --entry-file scripts/analyze.py --entry-line 50 \
  --max-nodes 100000 --timeout 20 \
  --graph-output graph_b.json > context_b.md

# 3. 合併成統一 graph
scip-graph-merge graph_a.json graph_b.json -o unified.json

# 4. 查詢：修改 run() 後哪些測試受影響？
scip-graph-query --graph unified.json \
  --test-impact 'BacktestEngine#run().'

# 5. 查詢：test_run 覆蓋了哪些 production code？
scip-graph-query --graph unified.json \
  --coverage 'TestBacktest#test_run().'
```

**注意事項：**
- 每次修改程式碼後需重新執行 `npx @sourcegraph/scip-python index .` 更新索引
- 重新建立索引後，舊的 graph JSON 無法與新索引的 graph 合併（SCIP hash 不同）
- `--graph-output` 會覆寫目標檔案，不會自動合併，需透過 `scip-graph-merge` 整合
- node key 為 SCIP symbol 的 descriptor 部分，可用 `--raw-symbols` 查看完整 symbol 以確認 key 格式

---

## 情境 9：批次測試提取

> 一次提取多個測試函式的上下文，適用於 CI 中自動收集受影響測試的深層上下文。

**操作方式：** command line

**使用場景：** 有多個測試檔案或測試方法需要批次提取時，可透過 `--test-file-pattern` 與 `--test-method-pattern` 搭配使用，取代逐一指定 `--entry-file` / `--entry-line`。

**指令：**
```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --test-file-pattern "test_runner*" \
  --test-method-pattern "*basic*" \
  --max-nodes 100000 \
  --timeout 20 \
  > batch_context.md
```

**預期結果：**
- 匹配 `test_runner*` 檔案中名稱含 `basic` 的測試方法
- stdout 輸出所有匹配測試的 Markdown 上下文
- 兩個 pattern 為聯合過濾（AND 關係）

> ⚠️ `--test-file-pattern` / `--test-method-pattern` 與 `--entry-file` / `--entry-line` 為互斥模式，不可同時使用。

---

## 情境 10：過濾控制 — Local Variable 與 Field Symbols

> BFS 預設排除 `local *` symbol 與 field/property symbols。透過 `--no-default-excludes` 可追蹤 local variable，透過 `--include-fields` 可包含 field symbols。

**操作方式：** command line

**使用場景：** 除錯時需要觀察 local variable 的傳遞路徑、需追蹤 field/property 的資料流，或需自訂排除規則時。

**指令：**

停用預設排除，追蹤所有 symbol（含 local variable）：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --no-default-excludes \
  > full_context.md
```

停用預設排除，但自訂排除 test 相關 symbol：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --no-default-excludes \
  --exclude-patterns "*test*" \
  > filtered_context.md
```

包含 field/property symbols（預設排除）：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --include-fields \
  --graph-output with_fields.json \
  > context_with_fields.md
```

**預期結果：**
- `--no-default-excludes` 移除 `local *` 的預設排除
- `--exclude-patterns` 可搭配 `--no-default-excludes` 使用，兩者獨立生效
- `--include-fields` 在 BFS 中包含 field/property symbols（descriptor 以 `.` 結尾且不含 `()`），type symbols（descriptor 以 `#` 結尾）仍排除
- `--include-fields` 與 `--no-default-excludes` 可獨立或同時使用

---

## 情境 11：完整輸出模式 — Dedup 控制與 Raw Symbols

> 預設啟用 containment dedup，同時作用於 Markdown 和 Graph JSON 輸出（子節點被父節點包含時合併）。如需查看完整未合併的結果，可停用。同時可啟用 raw symbols 顯示完整 SCIP symbol。

**操作方式：** command line

**使用場景：** 需要精確定位每個 code block 的邊界，或需要完整 SCIP symbol 前綴（如 `scip-python python pkg ...`）進行跨語言比對時。

**指令：**
```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --no-dedup \
  --raw-symbols \
  > detailed_context.md
```

**預期結果：**
- `--no-dedup` 停用 containment dedup（同時影響 Markdown 和 Graph JSON），所有收集到的 code block 均保留
- `--raw-symbols` 使 section header 顯示完整 SCIP symbol（含 scheme 前綴）

---

## 情境 12：多模組專案的 Symbol 過濾

> 限制 BFS 只追蹤特定模組內的 symbol，過濾掉第三方套件或不相關模組的呼叫。

**操作方式：** command line

**使用場景：** 大型專案中僅關注特定模組的相依關係，避免 BFS 展開到第三方套件。

**指令：**

單一模組：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --project-modules myapp \
  > myapp_context.md
```

多模組搭配排除 helper：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --project-modules myapp,utils \
  --exclude-patterns "*helper*" \
  > filtered_context.md
```

**預期結果：**
- `--project-modules` 接受逗號分隔的模組名稱（comma-separated），僅追蹤匹配模組內的 symbol
- 可搭配 `--exclude-patterns` 進一步排除特定 symbol
- 未匹配任何模組 symbol 時，`collected_nodes` 為 0

---

## 情境 13：分層探索 — 迭代式深層上下文提取

> 當代碼庫龐大時，一次性展開所有節點可能產生過多上下文。分層探索策略讓使用者先取得第一層概觀，人工判斷重要節點後，再針對性展開第二層。

**操作方式：** command line（兩階段手動操作）

**操作前置作業：** 完成安裝 scip-deep-context 與建立 SCIP 索引

**步驟 1：第一層提取（概觀）**

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 42 \
  --max-nodes 20 \
  --timeout 10 \
  --graph-output layer1_graph.json \
  > layer1_context.md
```

此步驟會產出包含 entry point 及其直接相依的淺層上下文。檢閱 `layer1_context.md` 中的函式，**人工判斷哪些節點值得深入探索**。

**步驟 2：第二層展開（深入）**

選定重要節點（例如 `BacktestEngine#run()` 在 `src/backtest.py` 第 100 行），以該節點為新的 entry point 再次提取：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/backtest.py \
  --entry-line 100 \
  --max-nodes 50 \
  --timeout 10 \
  --graph-output layer2_graph.json \
  > layer2_context.md
```

可選擇合併兩層的 graph：

```bash
scip-graph-merge layer1_graph.json layer2_graph.json -o combined_graph.json
```

**關鍵要點：**
- 「判斷哪些節點值得深入」是**人工決策步驟**，工具不會自動決定
- 每次提取使用較小的 `--max-nodes` 控制上下文量（配額僅用於 function-like symbols，field 不佔用）
- 可重複此流程，逐層深入直到獲得足夠的上下文
- 使用 `--graph-output` 記錄每層的 graph，最終可合併為完整的呼叫圖
- `is_partial` 欄位可幫助判斷哪些節點的代碼範圍不完整，可能需要重新以該節點為 entry point 展開

---

## 附錄：完整 CLI 參數表

**scip-extract 參數**

| 參數 | 類型 | 必要 | 預設值 | 說明 | 使用情境 |
|------|------|:----:|--------|------|---------|
| `--scip-file` | string | ✅ | — | SCIP 索引檔路徑 | 情境 1-13 |
| `--project-root` | string | ✅ | — | 專案根目錄 | 情境 1-13 |
| `--entry-file` | string | | — | 進入點檔案路徑（相對於 project-root） | 情境 1, 2, 10, 11, 12, 13 |
| `--entry-line` | integer | | — | 進入點行號（可指向定義行或引用行） | 情境 1, 2, 10, 11, 12, 13 |
| `--max-nodes` | integer | | 10 | BFS 最大展開節點數 | 情境 1-13 |
| `--timeout` | float | | 3.0 | 超時秒數 | 情境 1-13 |
| `--exclude-patterns` | string | | `""` | 排除的 symbol pattern，逗號分隔（預設排除 `local *`） | 情境 1, 10, 12 |
| `--no-default-excludes` | flag | | false | 停用預設排除 pattern（如 `local *`） | 情境 10 |
| `--test-file-pattern` | string | | — | 批次 extract：模糊搜尋測試檔名（glob pattern） | 情境 9 |
| `--test-method-pattern` | string | | — | 批次 extract：模糊搜尋測試方法名（glob pattern） | 情境 9 |
| `--project-modules` | string | | `""` | 專案模組名稱，逗號分隔（用於內外部判定） | 情境 12 |
| `--no-dedup` | flag | | false | 停用 containment dedup（同時影響 Markdown 和 Graph JSON），輸出所有收集到的區塊 | 情境 11 |
| `--raw-symbols` | flag | | false | section header 顯示完整 SCIP symbol（預設只顯示 descriptor） | 情境 11 |
| `--graph-output` | string | | — | 同時輸出 call graph JSON 到指定路徑 | 情境 2, 8, 13 |
| `--include-fields` | flag | | false | 在 BFS 中包含 field/property symbols（預設排除） | 情境 10 |
| `--version` | flag | | — | 顯示版本號 | — |

> ⚠️ `--entry-file` / `--entry-line` 與 `--test-file-pattern` / `--test-method-pattern` 為互斥模式：前者用於單一進入點提取（情境 1, 2, 10, 11, 12, 13），後者用於批次測試提取（情境 9）。兩者不可同時使用。

**scip-graph-merge 參數**

| 參數 | 類型 | 必要 | 預設值 | 說明 | 使用情境 |
|------|------|:----:|--------|------|---------|
| `inputs` (positional) | string+ | ✅ | — | 一個或多個 graph JSON 檔案路徑 | 情境 3, 8 |
| `-o` / `--output` | string | ✅ | — | 輸出合併後的 JSON 路徑 | 情境 3, 8 |

**scip-graph-query 參數**

| 參數 | 類型 | 必要 | 預設值 | 說明 | 使用情境 |
|------|------|:----:|--------|------|---------|
| `--graph` | string | ✅ | — | graph JSON 路徑（單一或合併後皆可） | 情境 4-7 |
| `--max-depth` | integer | | 10 | 最大追蹤深度 | 情境 4-7 |
| `--forward-from` | string | ✅* | — | Q1：正向查詢的起點 node key（支援 glob） | 情境 4 |
| `--reverse-from` | string | ✅* | — | Q2：反向查詢的起點 node key（支援 glob） | 情境 5 |
| `--test-impact` | string | ✅* | — | Q3：影響分析的目標 node key（支援 glob） | 情境 6 |
| `--coverage` | string | ✅* | — | Q4：覆蓋分析的測試 node key（支援 glob） | 情境 7 |
| `--list-nodes` | flag | ✅* | — | 列出 graph 中所有 node key | 情境 8 |

> *五種查詢模式互斥，必須指定其中一種。
