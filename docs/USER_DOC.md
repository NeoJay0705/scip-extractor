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

## Why SCIP Deep Context

在大型 codebase 中，理解一段代碼的完整上下文通常需要手動追蹤多層呼叫鏈：

| 痛點 | 傳統方式 | SCIP Deep Context |
|------|---------|-------------------|
| 跨檔案呼叫鏈追蹤 | 手動 grep → 逐檔 view → 反覆跳轉 | 一次 `scip-extract` 自動 BFS 展開 |
| 反向影響分析 | 逐檔搜尋呼叫者，易遺漏間接呼叫 | `--reverse-from` 自動追蹤所有層級 |
| 測試影響評估 | 人工判斷哪些測試需要跑 | `--test-impact` 精確列出受影響測試 |
| 跨語言符號解析 | grep 無法區分同名符號 | SCIP 索引提供語義級符號識別 |
| 重複分析工作 | 每次查詢重新追蹤 | Graph JSON 持久化，合併後反覆查詢 |

> 如果你的任務只涉及單檔案或純文字搜尋，`grep/view` 更適合。SCIP Deep Context 的價值在**跨檔案結構性分析**。

---

## 快速決策：何時使用哪個工具

| 觸發條件 | 需求 | 建議工具 | 對應情境 |
|---------|------|----------|---------|
| 需要理解函式 X 呼叫了什麼（超過 1 層） | 追蹤多層呼叫鏈 | `scip-extract` | [情境 1](#情境-1提取函式的深層上下文markdown)、[情境 13](#情境-13分層探索--迭代式深層上下文提取) |
| 想確認誰呼叫了某函式 | 反向查詢「誰呼叫了這個函式」 | `scip-graph-query --reverse-from` | [情境 5](#情境-5查詢--反向呼叫追蹤reverse) |
| 改了某函式，想知道影響哪些測試 | 分析「改了 X 會影響哪些測試」 | `scip-graph-query --test-impact` | [情境 6](#情境-6查詢--測試影響分析test-impact) |
| 想知道某測試覆蓋到哪些 production code | 分析「某測試覆蓋了哪些 production code」 | `scip-graph-query --coverage` | [情境 7](#情境-7查詢--測試覆蓋分析coverage) |
| 需要一次看完整跨檔上下文 | 一次取得跨檔案完整上下文 | `scip-extract`（可搭配 `--graph-output`） | [情境 1](#情境-1提取函式的深層上下文markdown)、[情境 2](#情境-2提取函式的-call-graphjson) |
| 有多個入口點結果，想整合後查詢 | 合併多個入口點的圖後再查詢 | `scip-graph-merge` + `scip-graph-query` | [情境 3](#情境-3合併多個-graph-json)、[情境 8](#情境-8端到端工作流程) |
| 只想看特定模組的代碼上下文 | Markdown 僅輸出指定模組的代碼 | `scip-extract --output-modules` | [情境 14](#情境-14模組級輸出過濾--output-modules) |
| 查詢呼叫鏈時想直接看源碼 | 查詢結果附帶源碼片段 | `scip-graph-query --with-source` | [情境 15](#情境-15查詢附帶源碼--with-source) |
| 只需要找字串、設定值、log 或註解 | 搜尋字串、設定值、log 或註解文字 | `grep` | — |
| 已知檔案路徑，只需快速閱讀片段 | 讀取已知路徑的檔案內容 | `view` | — |
| 先想知道專案有哪些檔案 | 快速查看目錄與檔案結構 | `glob` | — |
| 尚未建立 `index.scip` | 尚未建立 SCIP 索引 | 先依[前置作業](#建立-scip-索引)建索引，暫時使用 `grep/view` | [前置作業](#建立-scip-索引) |

## 標準操作流程

1. **前置**
   - 確認已安裝 CLI 並完成 `index.scip` 建置；若源碼已變更，先重建索引再操作。

2. **定位**
   - 先用 `grep/glob` 找到進入點的檔案與行號。函式定義行（`def`/`func`）與 body 行皆為有效進入點。

3. **提取**
   - 用 `scip-extract` 產生 Markdown 上下文與（可選）Graph JSON，作為後續查詢基礎。
   - 如需更細緻的上下文，可採用[情境 13 漸進式探索策略](#情境-13分層探索--迭代式深層上下文提取)逐步擴大分析範圍。

4. **分析**
   - 依需求使用 `scip-graph-query` 的 forward/reverse/test-impact/coverage，或先合併多個 graph 後再查詢。

5. **應用**
   - 從結果整理可執行的位置資訊（檔案路徑 + 行號範圍 + 目標符號），再進行修改、審查或測試規劃。

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
  --timeout 20 \
  > backtest_context.md
```

**參數說明：** 完整參數列表請見[附錄：完整 CLI 參數表](#附錄完整-cli-參數表)。

**預期結果：**
- stdout 輸出 Markdown 格式的深層上下文
- Markdown 開頭為 YAML frontmatter，包含 `collected_nodes`、`max_nodes`、`is_truncated`、`truncation_reasons`（截斷原因列表）、`duration_sec` 等欄位
- frontmatter 之後、Layer 0 代碼區段之前，插入 `## Summary` 區段，包含：
  - `### Modules`：各模組（SCIP package name）的節點數
  - `### Layer Distribution`：各 BFS layer 的節點數（0-count layer 跳過）
  - `### Truncated Branches`：僅截斷時出現，列出被丟棄的 pending symbols（去重後最多 10 個，超過顯示 `... and N more`）
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
| `metadata.context_file` | 對應的 Markdown 輸出檔名（`string|null`）；合併後作為 `source_layers` dict 的 key |
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
      "is_partial": false,
      "source_layers": { "": 0 }
    }
  },
  "is_truncated": false
}
```
- `nodes`：符合條件的節點（不含起點本身）
- `is_truncated`：`true` 表示 BFS 在 `max_depth` 處截斷，可能有更多節點
- 若 truncated，stderr 輸出警告訊息

> 💡 若需在查詢結果中直接查看源碼，可加上 `--with-source --project-root .`，輸出將從 JSON 切換為 Markdown 並附帶 code fence。詳見[情境 15](#情境-15查詢附帶源碼--with-source)。

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
- exit code 0：成功（所有匹配測試均無 broken links）
- exit code 1：有 broken links（任一測試的 BFS 產生 broken links，仍產出結果）
- exit code 2：無匹配的測試 symbol 或 SCIP 載入失敗

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
- `--no-default-excludes` 僅影響 BFS 過濾，**不影響進入點選擇**——進入點定位始終排除 `local *` symbols。即使啟用此 flag，`--entry-line` 指向僅含 local symbol 的行仍會觸發 `Only local symbols found` 錯誤（exit code 2）
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

## 情境 14：模組級輸出過濾（`--output-modules`）

> BFS 完整展開（Graph JSON 不受影響），但 Markdown 輸出僅包含指定模組的 code section。適用於大型專案中只關注特定模組上下文的場景。

**操作方式：** command line

**操作前置作業：** 完成安裝 scip-deep-context 與建立 SCIP 索引

**指令：**
```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --max-nodes 100 \
  --timeout 20 \
  --output-modules myapp \
  --graph-output full_graph.json \
  > myapp_only.md
```

多模組（逗號分隔）：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/main.py \
  --entry-line 10 \
  --max-nodes 100 \
  --output-modules myapp,utils \
  > myapp_utils.md
```

**預期結果：**
- Markdown 輸出僅包含匹配模組的 code section，frontmatter 新增 `rendered_nodes` 欄位（通過過濾後實際渲染的節點數）
- `collected_nodes` 仍為 BFS 總數（不受 `--output-modules` 影響）
- Graph JSON（`--graph-output`）保留完整 BFS 結果，不受 `--output-modules` 影響
- Summary 區段仍基於完整 BFS 結果（Modules 列表顯示所有模組）
- 無匹配時：frontmatter `rendered_nodes: 0` + Summary 區段 + 空正文（無 code section）
- exit code 與情境 1 相同

**`--output-modules` 與 `--project-modules` 的差異：**

| 參數 | 作用階段 | 影響範圍 | 用途 |
|------|---------|---------|------|
| `--project-modules` | BFS 展開 | 限制 BFS 追蹤範圍（資料過濾） | 排除第三方套件 |
| `--output-modules` | Markdown 渲染 | 限制 Markdown 輸出範圍（展示過濾） | 聚焦特定模組上下文 |

> ⚠️ **模組名稱為 SCIP package name**，非語言原生的 module path。例如 Python 專案中，模組名可能是 `scip-deep-context`（含連字符）而非 `scip_deep_context`（底線）。可先執行一次不帶 `--output-modules` 的提取，從 Summary 的 `### Modules` 列表確認正確的模組名稱。

---

## 情境 15：查詢附帶源碼（`--with-source`）

> 查詢 call graph 時一次取得源碼片段，免除逐一 `view` 檔案的步驟。啟用後輸出從 JSON 切換為 Markdown。

**操作方式：** command line

**操作前置作業：** 透過情境 2 或情境 3 產出 graph JSON

**指令：**
```bash
scip-graph-query \
  --graph unified_graph.json \
  --forward-from 'main().' \
  --max-depth 3 \
  --with-source \
  --project-root .
```

**參數說明：**

| 參數 | 必要 | 說明 |
|------|:----:|------|
| `--with-source` | | 啟用源碼附帶模式（輸出切換為 Markdown） |
| `--project-root` | ⚠️ | 源碼根目錄路徑（`--with-source` 啟用時必填） |

**預期結果（stdout Markdown）：**
```markdown
---
query_type: forward_from
entry_node: "main()."
result_nodes: 5
is_truncated: false
---

## Query Result

### BacktestEngine#run().
`quant_factory/backtest.py` L100-L150

```python
def run(self):
    ...
```
```

- 輸出格式從 JSON 切換為 Markdown，包含 YAML frontmatter + `## Query Result` 區段
- 每個節點附帶 code fence（自動偵測語言）
- frontmatter 包含 `query_type`、`entry_node`、`result_nodes`、`is_truncated`
- 不帶 `--with-source` 時仍輸出 JSON（行為不變）
- `--with-source` 與 `--list-nodes` 互斥

**使用場景：** Agent 工作流中，需要查詢結果同時包含源碼上下文，一次取得可直接閱讀的完整資訊。

---

## 工具分工：SCIP CLI 與 grep/view

### SCIP CLI 的不可替代場景

- **跨檔案呼叫追蹤**：從單一 entry point 展開多層呼叫鏈，直接取得語意級 caller/callee 關係（參見情境 1、4、5、13）。
- **測試影響分析**：以結構化 graph 反向定位受影響測試，支援 `test-impact` 查詢（參見情境 6）。
- **測試覆蓋分析**：從測試節點正向展開，識別覆蓋到的 production code（參見情境 7）。
- **Call Graph 建構與重用**：提取一次後可多次查詢，或合併多個 graph 進行全域分析（參見情境 2、3、8）。

### grep/view 的不可替代場景

- **搜尋非代碼內容**：config、字串常量、log 訊息、註解內容等文字匹配。
- **搜尋 SCIP 索引不涵蓋的語言或檔案類型**：例如 Markdown、YAML、shell script。
- **已知路徑的快速讀取**：只需查看特定檔案片段，不需建構語意關係。
- **目錄結構探索**：快速了解專案佈局與檔案組織。
- **索引未就緒時的臨時作業**：`index.scip` 不存在或 CLI 不可用時，作為 fallback 工具。

### 典型協作模式

`grep/glob` 先定位入口 → `scip-extract` 建立語意上下文 → `scip-graph-query` 做深度分析 → `view` 補充非索引細節。

## 故障排除與 Fallback

| 條件 | 行為 |
|------|------|
| `index.scip` 不存在 | 先依[前置作業](#建立-scip-索引)建索引；未建索引前使用 `grep/view` |
| CLI 工具不可用 | 改用 `grep/view` 完成文字層級定位與閱讀 |
| 進入點定位失敗（exit code 非 0） | 優先改用函式定義行（`def`/`func`）或含函式呼叫的 body 行重試；仍失敗則改用 `grep/view` |
| 錯誤訊息 `Only local symbols found` | 行號指向的行僅含 local variable 賦值（如 `x = foo()` 中的 `x`），無 function-level symbol。改用函式定義行（`def`/`func`）或含函式呼叫的行作為進入點 |
| Markdown frontmatter 顯示 `collected_nodes: 1` | 視為 BFS 未展開，優先檢查行號與符號定位，再重新提取 |
| Query 結果 `is_truncated: true` | 調整 `--max-depth` 或改以較小範圍分段查詢，避免直接依截斷結果下結論 |
| Markdown frontmatter `is_truncated: true` | 參考 Summary 的 `### Truncated Branches` 列表了解被截斷的分支，再以截斷分支為新 entry point 進行分層探索（[情境 13](#情境-13分層探索--迭代式深層上下文提取)） |
| 需求是非代碼文字搜尋 | 直接使用 `grep`，不走 SCIP query 流程 |

## 關鍵注意事項

1. **索引時效性**：`index.scip` 必須與當前源碼同步；源碼更新後未重建索引，可能造成符號與行號錯位。
2. **行號 edge case**：進入點行號可指向函式定義行（`def`/`func`/`function` 等）或函式 body 行，兩者皆為有效進入點。對含 type annotation 的 `def foo() -> int:`，建議使用 body 首行（def 行 + 1），因為 SCIP 可能將 def 行解析為 type reference 符號而非函式定義。
3. **`is_truncated` 檢查**：不論是提取或查詢，都應檢查是否截斷；截斷結果代表分析可能不完整。
4. **查詢模式互斥**：`--forward-from`、`--reverse-from`、`--test-impact`、`--coverage`、`--list-nodes` 每次只能擇一使用。
5. **合併限制**：僅可合併來自同一版本 `index.scip` 的 graph；不同索引版本會造成符號 key 不一致。
6. **Local symbol 進入點過濾**：進入點選擇始終排除 `local *` symbols（如變數賦值），此行為獨立於 `--no-default-excludes`（該 flag 僅控制 BFS 過濾）。若指向的行僅含 local symbols，將產出 `Only local symbols found` 錯誤並建議改選其他行。

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
| `--exclude-patterns` | string | | `""` | 排除的 symbol pattern，逗號分隔（預設排除 `local *`） | 情境 10, 12 |
| `--no-default-excludes` | flag | | false | 停用預設排除 pattern（如 `local *`） | 情境 10 |
| `--test-file-pattern` | string | | — | 批次 extract：模糊搜尋測試檔名（glob pattern） | 情境 9 |
| `--test-method-pattern` | string | | — | 批次 extract：模糊搜尋測試方法名（glob pattern） | 情境 9 |
| `--project-modules` | string | | `""` | 專案模組名稱，逗號分隔（用於內外部判定） | 情境 12 |
| `--no-dedup` | flag | | false | 停用 containment dedup（同時影響 Markdown 和 Graph JSON），輸出所有收集到的區塊 | 情境 11 |
| `--raw-symbols` | flag | | false | section header 顯示完整 SCIP symbol（預設只顯示 descriptor） | 情境 11 |
| `--graph-output` | string | | — | 同時輸出 call graph JSON 到指定路徑 | 情境 2, 8, 13, 14 |
| `--include-fields` | flag | | false | 在 BFS 中包含 field/property symbols（預設排除） | 情境 10 |
| `--output-modules` | string | | `""` | 逗號分隔的模組名稱（SCIP package name），僅過濾 Markdown 輸出（BFS 與 Graph JSON 不受影響）；啟用時 frontmatter 新增 `rendered_nodes` 欄位 | 情境 14 |
| `--version` | flag | | — | 顯示版本號 | — |

> ⚠️ `--entry-file` / `--entry-line` 與 `--test-file-pattern` / `--test-method-pattern` 為互斥模式：前者用於單一進入點提取（情境 1, 2, 10, 11, 12, 13, 14），後者用於批次測試提取（情境 9）。兩者不可同時使用。

**scip-graph-merge 參數**

| 參數 | 類型 | 必要 | 預設值 | 說明 | 使用情境 |
|------|------|:----:|--------|------|---------|
| `inputs` (positional) | string+ | ✅ | — | 一個或多個 graph JSON 檔案路徑 | 情境 3, 8 |
| `-o` / `--output` | string | ✅ | — | 輸出合併後的 JSON 路徑 | 情境 3, 8 |

**scip-graph-query 參數**

| 參數 | 類型 | 必要 | 預設值 | 說明 | 使用情境 |
|------|------|:----:|--------|------|---------|
| `--graph` | string | ✅ | — | graph JSON 路徑（單一或合併後皆可） | 情境 4-7, 15 |
| `--max-depth` | integer | | 10 | 最大追蹤深度 | 情境 4-7, 15 |
| `--forward-from` | string | ✅* | — | Q1：正向查詢的起點 node key（支援 glob） | 情境 4, 15 |
| `--reverse-from` | string | ✅* | — | Q2：反向查詢的起點 node key（支援 glob） | 情境 5 |
| `--test-impact` | string | ✅* | — | Q3：影響分析的目標 node key（支援 glob） | 情境 6 |
| `--coverage` | string | ✅* | — | Q4：覆蓋分析的測試 node key（支援 glob） | 情境 7 |
| `--list-nodes` | flag | ✅* | — | 列出 graph 中所有 node key | 情境 8 |
| `--with-source` | flag | | false | 啟用源碼附帶模式（輸出從 JSON 切換為 Markdown）；與 `--list-nodes` 互斥 | 情境 15 |
| `--project-root` | string | ⚠️ | — | 源碼根目錄路徑（`--with-source` 啟用時必填） | 情境 15 |

> *五種查詢模式互斥，必須指定其中一種。  
> ⚠️ `--with-source` 與 `--list-nodes` 互斥。`--with-source` 啟用時 `--project-root` 為必填。
