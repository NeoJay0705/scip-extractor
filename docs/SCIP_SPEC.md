# SCIP Deep Context 技術規格書

> 本文件為 scip-deep-context 工具鏈的正式技術規格，記錄安裝規格、CLI 介面契約、資料格式、Agent Skill 介面。  
> 關聯文件：[USER_DOC.md](./USER_DOC.md)、[AGENT_SKILL.md](./AGENT_SKILL.md)、[skill_manifest.yaml](./skill_manifest.yaml)  
> 需求來源：REQ-01 ~ REQ-05（`neo_opus_11_spec_final.md`）

---

## 一、安裝規格

### 1.1 安裝方式

| 方式 | 指令 | 適用場景 | 關聯情境 |
|------|------|---------|---------|
| 主要安裝（推薦） | `pipx install ./scip-deep-context` | 一般使用者 | 情境 1-12 |
| Fallback | `pip install --user ./scip-deep-context` | 無 pipx 環境 | 情境 1-12 |
| 開發者模式 | `pip install -e ./scip-deep-context` | 需修改源碼 | — |

**原因**：以 `pipx` 為主要安裝方式，避免 virtualenv 啟動依賴（REQ-01），使非 Python 專案亦可直接使用 CLI 工具。

### 1.2 CLI Entry Points

安裝後提供三個 CLI 指令：

| 指令 | Entry Point | 說明 |
|------|------------|------|
| `scip-extract` | `scip_deep_context.cli:main` | 從 SCIP 索引提取深層上下文 |
| `scip-graph-merge` | `scip_deep_context.cli:merge_main` | 合併多個 graph JSON |
| `scip-graph-query` | `scip_deep_context.cli:query_main` | 查詢 call graph |

---

## 二、語言支援

### 2.1 SCIP Indexer 支援

| 語言 | Indexer 套件 | 最低環境要求 | 索引指令 | 關聯情境 |
|------|------------|------------|---------|---------|
| Python | `@sourcegraph/scip-python` | Python 3.x + npm | `npx @sourcegraph/scip-python index .` | 情境 1-12 |
| Golang | `scip-go` | Go 1.17+ | `scip-go` | 情境 1-12 |
| TypeScript | `@sourcegraph/scip-typescript` | Node.js 18+ / TS 5+ | `npx scip-typescript index` | 情境 1-12 |

**原因**：REQ-02 要求支援三種語言的前置作業文件。SCIP 為語言無關的索引格式，上述三種 indexer 為目前生態系中可用的官方 indexer。

### 2.2 索引產出

- 產出檔案：`index.scip`（protobuf binary 格式）
- 位置：專案根目錄
- 驗證條件：檔案存在且 file size > 0

---

## 三、CLI 介面規格

### 3.1 scip-extract

**用途**：從指定進入點出發，BFS 展開呼叫圖，產出 Markdown 上下文（stdout）與可選的 Graph JSON。BFS 預設僅追蹤 function-like symbols（descriptor 含 `()` 且不以 `.(param)` 格式結尾的 symbol）。Parameter symbols（格式 `method().(param)`）雖含 `()`，但屬參數而非方法，排除於 BFS 追蹤。field/property/variable/class 預設排除。可透過 `--include-fields` flag 包含 field symbols。

#### 參數

| 參數 | 類型 | 必要 | 預設值 | 約束 |
|------|------|:----:|--------|------|
| `--scip-file` | string | ✅ | — | 必須為有效的 SCIP protobuf 檔案 |
| `--project-root` | string | ✅ | — | 必須為存在的目錄路徑 |
| `--entry-file` | string | ⚠️† | — | 與 `--entry-line` 搭配使用 |
| `--entry-line` | integer | ⚠️† | — | 與 `--entry-file` 搭配使用；行號可指向函式定義行（`def`/`func`/`function` 等）或函式 body 行（type annotation edge case 詳見 [USER_DOC.md 關鍵注意事項](./USER_DOC.md#關鍵注意事項)） |
| `--test-file-pattern` | string | ⚠️‡ | — | glob pattern |
| `--test-method-pattern` | string | ⚠️‡ | — | glob pattern |
| `--max-nodes` | integer | | 10 | ≥ 1 |
| `--timeout` | float | | 3.0 | > 0 |
| `--exclude-patterns` | string | | `""` | 逗號分隔；預設排除 `local *` |
| `--no-default-excludes` | flag | | false | 停用 `local *` BFS 預設排除（不影響進入點選擇，進入點始終排除 `local *`） |
| `--project-modules` | string | | `""` | 逗號分隔（不支援空格分隔多值） |
| `--no-dedup` | flag | | false | 停用 containment dedup（同時影響 Markdown 和 Graph JSON） |
| `--raw-symbols` | flag | | false | section header 顯示完整 SCIP symbol |
| `--graph-output` | string | | — | 輸出路徑；覆寫現有檔案 |
| `--include-fields` | flag | | false | 在 BFS 中包含 field/property symbols（預設排除） |
| `--output-modules` | string | | `""` | 逗號分隔的模組名稱，僅過濾 Markdown 輸出（BFS 與 Graph JSON 不受影響）。模組名稱為 SCIP package name（非語言原生 module path）。⚠️ 單 package 專案中為全選或全不選 |
| `--output-symbol-prefix` | string | | `""` | 逗號分隔的 descriptor prefix 列表，僅過濾 Markdown 輸出（BFS 與 Graph JSON 不受影響）。prefix 間 OR、與 `--output-modules` 為 AND。匹配規則：`descriptor.startswith(prefix)`，區分大小寫、strip 空白、忽略空 token、靜默去重 |
| `--version` | flag | | — | 顯示版本號 |

> † **進入點模式**：`--entry-file` + `--entry-line` 必須同時出現。  
> ‡ **批次模式**：`--test-file-pattern` 和/或 `--test-method-pattern`。  
> **兩種模式互斥**，必須且只能使用其中一種。關聯情境：進入點模式（情境 1, 2, 10, 11, 12, 13, 14）、批次模式（情境 9）。

**原因**：兩種模式的 BFS 起點取得方式不同——進入點模式從單一 symbol 開始，批次模式從 pattern 匹配的多個測試 symbol 開始。合併兩者會造成語義模糊。

#### Exit Codes

| Code | 含義 | 說明 | 關聯情境 |
|------|------|------|---------|
| 0 | 成功 | 無 broken links | 情境 1, 2, 8-13 |
| 1 | 部分成功 | 有 broken links，仍產出結果 | 情境 1, 9 |
| 2 | 失敗 | SCIP 載入或進入點定位失敗（含 local-only 行特化錯誤、批次模式無匹配測試 symbol） | 情境 1, 9, 10 |
| 3 | 失敗 | 檔案路徑解析失敗 | 情境 1 |

### 3.2 scip-graph-merge

**用途**：合併多個 graph JSON 為統一 graph。

#### 參數

| 參數 | 類型 | 必要 | 預設值 | 約束 |
|------|------|:----:|--------|------|
| `inputs`（positional） | string+ | ✅ | — | 至少 1 個有效的 graph JSON |
| `-o` / `--output` | string | ✅ | — | 輸出路徑 |

#### 合併規則

| # | 規則 | 說明 | 關聯情境 |
|---|------|------|---------|
| 1 | SCIP Hash 驗證 | 所有輸入必須來自同一份 `index.scip`（SHA256 比對），否則 `IndexHashMismatchError` | 情境 3 |
| 2 | 節點聯集 | 相同 key 的節點保留一份，`is_test` 取 OR | 情境 3 |
| 3 | Layer 轉換 | 單一 graph 的 `layer` → 合併後的 `source_layers` dict（key 為 `context_file`） | 情境 3 |
| 4 | 邊去重 | `(from, to, type)` 唯一，按字母排序 | 情境 3 |
| 5 | 增量合併 | 已合併的 graph 可再與其他 graph 合併 | 情境 3 |
| 6 | `is_partial` 取 OR | 合併時 `is_partial` 取 OR（任一來源為 partial 則結果為 partial） | 情境 3 |

**原因**：合併規則確保來自不同進入點的 graph 可安全整合為統一圖，同時保留各來源的 BFS 層級資訊（`source_layers`）。

#### Exit Codes

| Code | 含義 | 關聯情境 |
|------|------|---------|
| 0 | 合併成功 | 情境 3 |
| 1 | SCIP hash 不匹配 | 情境 3 |
| 2 | 其他錯誤（如檔案不存在） | 情境 3 |

### 3.3 scip-graph-query

**用途**：在 call graph 上執行查詢。

#### 參數

| 參數 | 類型 | 必要 | 預設值 | 約束 |
|------|------|:----:|--------|------|
| `--graph` | string | ✅ | — | 有效的 graph JSON（單一或合併後皆可） |
| `--max-depth` | integer | | 10 | ≥ 1 |
| `--list-nodes` | flag | ✅* | — | 五種模式互斥 |
| `--forward-from` | string | ✅* | — | 支援 glob pattern |
| `--reverse-from` | string | ✅* | — | 支援 glob pattern |
| `--test-impact` | string | ✅* | — | 支援 glob pattern |
| `--coverage` | string | ✅* | — | 支援 glob pattern |

> *五種查詢模式互斥，必須指定其中一種。

**附加參數：**

| 參數 | 類型 | 必要 | 預設值 | 約束 |
|------|------|:----:|--------|------|
| `--with-source` | flag | | false | 啟用時輸出從 JSON 切換為 Markdown（附帶源碼片段）；與 `--list-nodes` 互斥 |
| `--project-root` | string | ⚠️ | — | 源碼根目錄路徑；`--with-source` 啟用時必填 |

> ⚠️ `--with-source` 與 `--list-nodes` 互斥，同時啟用時 argparse 報錯。`--with-source` 可與 `--forward-from`、`--reverse-from`、`--test-impact`、`--coverage` 四種查詢模式搭配。

#### 查詢行為

| 模式 | BFS 方向 | 結果過濾 | 附加輸出 | 說明 | 關聯情境 |
|------|---------|---------|---------|------|---------|
| `--forward-from` | 正向 | 無 | — | 找出 callee 鏈 | 情境 4 |
| `--reverse-from` | 反向 | 無 | — | 找出 caller 鏈 | 情境 5 |
| `--test-impact` | 反向 | `is_test=true` | `warnings: ["no_test_nodes_in_graph"]`（條件） | 找出受影響的測試。⚠️ graph 需含 test nodes（`is_test=true`）；空結果且整張 graph 無 test nodes 時觸發 warning | 情境 6 |
| `--coverage` | 正向 | `is_test=false` | `warnings: ["target_is_not_test_function"]`（條件） | 找出被覆蓋的 production code。⚠️ 預期目標為測試函式（`is_test=true`）；非測試目標時退化為 `--forward-from` 語義，僅新增 warning 不改結果集 | 情境 7 |
| `--list-nodes` | — | — | — | 列出所有節點 key | 情境 8 |

**截斷行為**：BFS 在 `max_depth` 處截斷時，回傳 `is_truncated: true` 及 `truncated_branches`（去重、BFS 發現順序排列的被截斷分支 node keys），stderr 輸出 `Warning: result truncated at max_depth=N`。`warnings` 亦同步輸出至 stderr（每個 warning 一行）。

**原因**：五種模式覆蓋程式碼追蹤的典型需求——正向/反向追蹤、測試影響評估、覆蓋率分析。glob pattern 支援讓使用者無需知道完整 symbol 即可查詢。

---

## 四、資料格式規格

### 4.1 單一 Graph JSON

```json
{
  "metadata": {
    "scip_index_hash": "sha256:<hex>",
    "entry_file": "<path>",
    "entry_line": "<int>",
    "entry_symbol": "<descriptor>",
    "context_file": "<string|null>"
  },
  "nodes": {
    "<descriptor>": {
      "file": "<path>",
      "lines": ["<start>", "<end>"],
      "layer": "<int>",
      "is_test": "<bool>",
      "is_partial": "<bool>"
    }
  },
  "edges": [
    { "from": "<descriptor>", "to": "<descriptor>", "type": "reference" }
  ]
}
```

**欄位定義**：

| 欄位 | 說明 |
|------|------|
| `metadata.scip_index_hash` | SCIP 索引檔的 SHA256 雜湊，用於合併時驗證來源一致性 |
| `metadata.entry_symbol` | 進入點 symbol descriptor |
| `metadata.context_file` | 對應的 Markdown 輸出檔名（`string|null`）；合併後作為 `source_layers` dict 的 key |
| `nodes[].layer` | BFS 層級（0 = entry point） |
| `nodes[].is_test` | 是否為測試節點（依 SymbolRole.TEST 或檔案路徑 pattern 判定） |
| `nodes[].is_partial` | 是否為部分擷取（`true` 表示代碼範圍不完整）。預設值：`false` |
| `edges[].type` | 邊類型，`"reference"`（呼叫引用）或 `"implementation"`（介面實作） |

### 4.2 合併後 Graph JSON

```json
{
  "metadata": {
    "scip_index_hash": "sha256:<hex>",
    "sources": [
      { "entry_symbol": "<descriptor>", "context_file": "<string|null>" }
    ]
  },
  "nodes": {
    "<descriptor>": {
      "file": "<path>",
      "lines": ["<start>", "<end>"],
      "is_test": "<bool>",
      "is_partial": "<bool>",
      "source_layers": { "<context_file_or_empty>": "<int>" }
    }
  },
  "edges": [
    { "from": "<descriptor>", "to": "<descriptor>", "type": "reference" }
  ]
}
```

**與單一 Graph 的差異**：合併後 `metadata` 中 `entry_file`/`entry_line`/`entry_symbol` 被 `sources` 陣列取代；節點的 `layer` 被 `source_layers` dict 取代。

### 4.3 Query 輸出格式

#### 4.3.1 預設 JSON 輸出

不啟用 `--with-source` 時，輸出 JSON（維持既有契約）：

```json
{
  "nodes": { "..." : "..." },
  "is_truncated": true,
  "truncated_branches": [
    "DataLoader#load().",
    "Optimizer#step()."
  ],
  "warnings": ["no_test_nodes_in_graph"]
}
```

| 欄位 | 類型 | 必要性 | 說明 |
|------|------|:------:|------|
| `nodes` | object | 必要 | 符合條件的節點（不含起點本身） |
| `is_truncated` | bool | 必要 | `true` 表示 BFS 在 `max_depth` 處截斷 |
| `truncated_branches` | list[str] | 必要 | 被 `max_depth` 截斷的分支 node keys（去重、BFS 發現順序）；未截斷時為空陣列 `[]` |
| `warnings` | list[str] | 條件 | 查詢警告陣列。`test_impact` 空結果 + graph 無 test nodes 時含 `"no_test_nodes_in_graph"`；`coverage` 目標非測試函式時含 `"target_is_not_test_function"`。無 warning 時此欄位不出現 |

#### 4.3.2 With-source Markdown 輸出（條件模式）

啟用 `--with-source` 時，輸出切換為 Markdown，格式與 `scip-extract` 輸出風格一致：

```markdown
---
query_type: forward_from
entry_node: "main()."
result_nodes: 5
is_truncated: true
warnings:
- no_test_nodes_in_graph
---

> ⚠️ Warning: no_test_nodes_in_graph

### Truncated Branches
- `DataLoader#load().`
- `Optimizer#step().`
- ... and 3 more

## Query Result

### BacktestEngine#run().
`quant_factory/backtest.py` L100-L150

```python
def run(self):
    ...
```
```

**frontmatter 欄位**：

| 欄位 | 類型 | 必要性 | 說明 |
|------|------|:------:|------|
| `query_type` | string | 必要 | 查詢類型（`forward_from` / `reverse_from` / `test_impact` / `coverage`） |
| `entry_node` | string | 必要 | 查詢起點 node key |
| `result_nodes` | int | 必要 | 結果節點數 |
| `is_truncated` | bool | 必要 | 是否截斷 |
| `warnings` | list[str] | 條件 | 查詢警告（同 §4.3.1 `warnings` 語義）；無 warning 時不出現 |

**Markdown 正文渲染順序**：

1. **Warnings blockquote**（條件）：`warnings` 非空時，輸出 `> ⚠️ Warning: {warning}`，每個 warning 一行
2. **Truncated Branches 區段**（條件）：`truncated_branches` 非空時，輸出 `### Truncated Branches` + bullet list（最多 10 個，超過顯示 `... and N more`）
3. **Query Result 區段**：`## Query Result` + 各節點 code fence

**原因**：`--with-source` 為條件式輸出模式切換——預設不改變 JSON 行為，啟用時為 Agent 提供可直接閱讀的 Markdown 上下文，消除逐一 `view` 源檔的步驟。warnings 與 truncated branches 的 Markdown 渲染確保查詢的完整診斷資訊以人類可讀格式呈現。關聯情境：情境 15。

### 4.4 Markdown 輸出格式

- 開頭為 YAML frontmatter（`---` 分隔），包含：
  - `collected_nodes`：收集到的節點數（BFS 總數，不受 `--output-modules` 影響）
  - `max_nodes`：BFS 最大展開節點數（對應 `--max-nodes` 參數值）
  - `is_truncated`：是否因 max_nodes 或 timeout 而截斷
  - `truncation_reasons`：截斷原因列表（如 `["max_nodes"]`、`["timeout"]`），未截斷時為空陣列
  - `duration_sec`：執行耗時
  - `rendered_nodes`：通過輸出過濾後實際渲染的節點數（任一輸出過濾參數——`--output-modules` 或 `--output-symbol-prefix`——啟用時出現；兩者並用時為 AND 過濾後的節點數）
- frontmatter 之後、Layer 0 代碼區段之前，插入 `## Summary` 區段（見下方格式）
- 主體為 code section，每個 section 對應一個被追蹤到的 symbol

#### Summary 區段格式

```markdown
## Summary

### Modules
- `myapp`: 15
- `utils`: 8

### Layer Distribution
- Layer 0: 1
- Layer 1: 7
- Layer 2: 12
- Layer 3: 3

### Truncated Branches
- `BacktestEngine#run().`
- `DataLoader#load().`
- ... and 5 more
```

| 子區段 | 必要性 | 說明 |
|--------|:------:|------|
| `### Modules` | 必要 | 各 SCIP package 的節點數（依 `parse_package()` 提取模組名） |
| `### Layer Distribution` | 必要 | 各 BFS layer 的非零節點數（0-count layer 跳過） |
| `### Truncated Branches` | 條件必要 | 僅截斷時出現；列出去重後的 pending symbols（最多 10 個，超過顯示 `... and N more`） |

**原因**：Summary 區段提供人類可讀的結構化摘要，與 frontmatter 的機器可解析欄位互補。Agent 可從 Modules 列表確認 `--output-modules` 或 `--project-modules` 的正確值，從 Truncated Branches 選擇下一個分層探索目標。關聯情境：情境 1、13、14。

### 4.5 向後相容性聲明

`is_partial` 欄位為 **加法變更**（additive change），對既有消費者無破壞性影響：

- **JSON 消費者**：未讀取 `is_partial` 的既有程式碼可安全忽略此欄位（JSON 標準行為——忽略未知欄位）
- **Markdown 消費者**：`*(partial extraction)*` 標記為新增文字標註，不影響既有 section 結構解析
- **合併消費者**：`is_partial` 的 OR 合併語義與 `is_test` 一致，不改變既有合併行為

**Function-like BFS 過濾**（v0.4.0 行為變更）：

- BFS 預設僅追蹤 function-like symbols（descriptor 含 `()` 的 symbol），field/property/variable/class 節點不再出現在 graph JSON `nodes` 中
- 此為 **預期行為變更**，目的為精簡 BFS 結果、避免 field 佔用 `--max-nodes` 配額
- 可透過 `--include-fields` flag 恢復舊行為（包含 field symbols）

**原因**：REQ-07（新增 `is_partial`）與 REQ-08（合併策略）為功能增強，選擇加法變更策略以確保既有工具鏈無需修改即可繼續運作。REQ-01（function-like 過濾）為行為變更，透過 `--include-fields` 提供向後相容選項。關聯情境：情境 2（Graph JSON 提取）、情境 3（合併）。

**Parameter Symbol 排除（v0.5.0 行為變更）**：

- **Schema 相容**：JSON 欄位結構不變（`metadata`、`nodes`、`edges` 結構維持）、函數簽名不變
- **Data 相容**：節點集合因移除 parameter nodes 而變更：
  - 以 `method().(param)` 格式為 key 的節點不再出現於 `nodes` dict
  - 涉及 parameter node 的 edge 不再出現於 `edges` 陣列
  - 既有以 `method().(param)` 為查詢 key 的下游程式需移除或更新相關查詢
- **Graph JSON Dedup**：`--no-dedup` flag 語義擴展至同時影響 Markdown 和 Graph JSON 輸出

**Migration Note**：若下游系統曾依賴 parameter node key（如 `module/method().(param_name)`）進行查詢，需移除此類查詢——parameter 資訊已包含於父方法的代碼片段中，不再作為獨立節點暴露。

**Summary 區段與 Frontmatter 擴充（v0.6.0 加法變更）**：

- **`truncation_reasons` 欄位**：frontmatter 新增截斷原因列表，未讀取此欄位的既有程式碼可安全忽略
- **`rendered_nodes` 欄位**：frontmatter 新增條件欄位（僅 `--output-modules` 啟用時出現），不影響既有 frontmatter 解析
- **`## Summary` 區段**：在 frontmatter 後插入新的 Markdown 區段，不改變既有 code section 結構
- **`pending_symbols`**：`TraversalResult` 新增欄位，加法變更，不影響既有 API

**`--with-source` 條件式輸出（v0.6.0）**：

- **預設行為不變**：`scip-graph-query` 不帶 `--with-source` 時仍輸出 JSON，完全向後相容
- **新模式**：`--with-source` 為顯式 opt-in，啟用時輸出切換為 Markdown
- **`--project-root` 條件必要**：僅 `--with-source` 啟用時必填，不影響既有查詢

**`--output-modules` 輸出過濾（v0.6.0）**：

- **BFS 與 Graph JSON 不受影響**：`--output-modules` 僅控制 Markdown 輸出展示範圍
- **不帶此參數時行為不變**：全部節點渲染至 Markdown（與既有行為一致）

**Query 結果 `truncated_branches` 與 `warnings` 欄位（v0.7.0 加法變更）**：

- **`truncated_branches`**：所有查詢模式（`forward_from`/`reverse_from`/`test_impact`/`coverage`）的 JSON 回傳值新增此欄位（`list[str]`），未截斷時為空陣列。未讀取此欄位的既有程式碼可安全忽略（JSON 標準行為——忽略未知欄位）
- **`warnings`**：`test_impact` 和 `coverage` 的 JSON 回傳值條件性新增此欄位（`list[str]`）。僅在觸發 warning 時出現，既有消費者可安全忽略
- **stderr 輸出**：新增 warnings 的 stderr 輸出（每個 warning 一行），不影響 stdout 的結構化輸出
- **Exit code 不變**：warnings 為診斷訊息，不改變任何 exit code 語義
- **Markdown 渲染**：`--with-source` 模式新增 `> ⚠️ Warning:` blockquote 和 `### Truncated Branches` 區段，不影響既有 `## Query Result` 結構

**原因**：`truncated_branches` 和 `warnings` 為可觀測性增強（INT-01/02/03），選擇加法變更策略以確保既有工具鏈無需修改即可繼續運作。關聯情境：情境 4-7、15。

**`--output-symbol-prefix` 新增參數與 `rendered_nodes` 觸發條件擴充（v0.8.0 加法變更）**：

- **`--output-symbol-prefix`**：新增 CLI 參數，純 additive 變更。既有 CLI 呼叫不含此參數時行為完全不變
- **`rendered_nodes` 觸發條件擴充**：由「僅 `--output-modules` 啟用時出現」擴充為「任一輸出過濾參數（`--output-modules` 或 `--output-symbol-prefix`）啟用時出現」。既有使用 `--output-modules` 的腳本行為不變（仍會出現 `rendered_nodes`）
- **`rendered_nodes` 決策矩陣**：

| 情境 | `--output-modules` | `--output-symbol-prefix` | `rendered_nodes` 行為 |
|------|:------------------:|:------------------------:|----------------------|
| 無過濾 | ✗ | ✗ | 不出現 |
| 僅 module 過濾 | ✓ | ✗ | 出現 |
| 僅 prefix 過濾 | ✗ | ✓ | 出現 |
| 兩者並用 | ✓ | ✓ | 出現（AND 過濾後的節點數） |

- **prefix 匹配規則**：`descriptor.startswith(prefix)`，區分大小寫、strip 空白、忽略空 token、靜默去重。使用者應先透過 Summary `### Modules` 或 `--raw-symbols` 確認實際 descriptor 格式

**原因**：`--output-symbol-prefix` 為 REQ-INT-01 新功能需求，提供 descriptor 層級的 Markdown 輸出過濾能力，特別解決單 SCIP package 專案中 `--output-modules` 無法細粒度過濾的問題。`rendered_nodes` 觸發條件擴充為語義一致性修正——任何啟用輸出過濾的情境均應報告實際渲染節點數。關聯情境：情境 14。

---

## 五、Agent Skill 介面契約

### 5.1 Skill 定義

三個 skill 定義於 `skill_manifest.yaml`，以框架無關的 YAML schema 描述。

| Skill | CLI 指令 | 輸出格式 | 關聯情境 |
|-------|---------|---------|---------|
| `scip-extract` | `scip-extract` | Markdown (stdout) + JSON (file) | 情境 1, 2, 8-14 |
| `scip-graph-query` | `scip-graph-query` | JSON (stdout) / Markdown (`--with-source`) | 情境 4-7, 15 |
| `scip-graph-merge` | `scip-graph-merge` | JSON (file) | 情境 3, 8 |

### 5.2 Schema 驗證

`skill_manifest.schema.json` 定義 manifest 結構約束：
- 必須包含恰好 3 個 skill
- 每個 skill 必須有 `name`、`description`、`cli_command`、`parameters`
- `cli_command` 值限定為 `scip-extract`、`scip-graph-merge`、`scip-graph-query`

### 5.3 System Prompt 模板

定義於 `AGENT_SKILL.md`，包含 7 個必要區段：

| 區段 | 內容 | 來源需求 |
|------|------|---------|
| Agent 角色定義 | 代碼追蹤助手，三種能力 | REQ-04 |
| 前置條件檢查 | `index.scip` 存在性，三語言 indexer 指令 | REQ-04 + REQ-02 |
| CLI 工具呼叫規則 | 6 種場景 × skill 對應表 | REQ-04 |
| 參數建議 | agent 場景 `max_nodes ≤ 200` | REQ-04 |
| 輸出格式解讀 | Markdown / JSON 結構說明 | REQ-04 |
| 錯誤處理指引 | exit code 0/1/2/3 對應動作 | REQ-04 |
| Token 優化建議 | 限制 max_nodes、優先 query 定位、project_modules 過濾 | REQ-04 |

---

## 六、情境映射表

| 情境 | 描述 | 涉及 CLI | 涉及規格章節 |
|:----:|------|---------|------------|
| 1 | 提取深層上下文（Markdown） | scip-extract | §3.1, §4.4 |
| 2 | 提取 Call Graph（JSON） | scip-extract | §3.1, §4.1 |
| 3 | 合併多個 Graph JSON | scip-graph-merge | §3.2, §4.2 |
| 4 | 正向呼叫追蹤（Forward） | scip-graph-query | §3.3, §4.3 |
| 5 | 反向呼叫追蹤（Reverse） | scip-graph-query | §3.3, §4.3 |
| 6 | 測試影響分析（Test Impact） | scip-graph-query | §3.3, §4.3 |
| 7 | 測試覆蓋分析（Coverage） | scip-graph-query | §3.3, §4.3 |
| 8 | 端到端工作流程 | 全部三個 | §3.1-3.3 |
| 9 | 批次測試提取 | scip-extract | §3.1 |
| 10 | 過濾控制 — Local Variable 與 Field Symbols | scip-extract | §3.1, §八 |
| 11 | Dedup 控制與 Raw Symbols | scip-extract | §3.1 |
| 12 | 多模組 Symbol 過濾 | scip-extract | §3.1 |
| 13 | 分層探索 — 迭代式深層上下文提取 | scip-extract, scip-graph-merge | §3.1, §3.2, §4.1, §4.2 |
| 14 | 模組級輸出過濾（`--output-modules` / `--output-symbol-prefix`） | scip-extract | §3.1, §4.4, §4.5 |
| 15 | 查詢附帶源碼 | scip-graph-query | §3.3, §4.3 |

---

## 七、Parameter Symbol BFS 進入機制說明

### 7.1 問題機制

SCIP index 中，method parameter 的 symbol 格式為 `method().(param)`，其 descriptor
包含 `()` 子字串（來自父方法 `method()`）。在 v0.4.x 及之前版本中，BFS 引擎的過濾
函數 `is_function_like()` 使用 `"()" in symbol` 判斷，無法區分此格式與真正的方法
descriptor `method().`，導致 parameter symbol 被誤判為 function-like 並進入 BFS 佇列。

### 7.2 根因鏈

1. `_find_children_in_block()` 掃描 symbol_table，找到參數 reference 在方法 body 行範圍內
2. `is_function_like("method().(param)")` 因 `"()" in symbol` 回傳 `True`
3. BFS 將參數建立為獨立節點，呼叫 `extract_source()` 擷取代碼
4. 參數 symbol 無 `enclosing_range`、定義行不以 `:` 結尾 → 落入 Fallback 3（±5 lines）
5. 多個參數的 ±5 lines 範圍高度重疊（實測 89% 重疊率）
6. Graph JSON 不套用 containment dedup，參數節點全數保留

### 7.3 可重現案例

**SCIP Index 中的實際 symbol**：

| Symbol（descriptor 部分） | 類型 | `is_function_like` 結果 |
|--------------------------|------|:----------------------:|
| `output_formatter/format_graph_json().` | Method | True ✓ |
| `output_formatter/format_graph_json().(entry_file)` | Parameter | True ✗（應為 False） |
| `output_formatter/format_graph_json().(entry_line)` | Parameter | True ✗（應為 False） |

**修改前行為**：
- 三個 symbol 均通過 `is_function_like()` → 進入 BFS → 各自建立節點
- 兩個 parameter 節點各佔 1 個 `max_nodes` 配額
- 產出代碼片段高度重疊且完全包含於父方法 block 內

**修改後期望行為**：
- `format_graph_json().` → True → 進入 BFS ✓
- `format_graph_json().(entry_file)` → False → 排除 ✓
- `format_graph_json().(entry_line)` → False → 排除 ✓

---

## 八、Local Symbol 進入點過濾機制說明

### 8.1 問題機制

SCIP index 中，local variable 的 symbol 以 `local ` 開頭（如 `local 16`），出現在函式 body
行的變數賦值位置。在 v0.4.x 及之前版本中，`locate_entry_symbol()` 未過濾 local symbols，
當使用者以 `--entry-line` 指向含 local variable 賦值的 body 行時，`local N` 可能因
leftmost character 選擇而被優先選為 entry symbol，導致 BFS 展開異常。

### 8.2 修復策略

在 `locate_entry_symbol()` 的候選收集迴圈中，local symbols 被前置過濾（`is_local_symbol()`
共用函式，定義於 `symbol_filter.py`）。此過濾獨立於 `--no-default-excludes`（後者僅控制
BFS `SymbolFilter`），確保進入點定位始終排除 local symbols。

### 8.3 行為對照

| 情境 | 修改前行為 | 修改後行為 |
|------|----------|----------|
| body 行含 `local N` + function reference | `local N` 可能被選為 entry（因 leftmost） | `local N` 被排除，function reference 被選取 |
| body 行僅含 `local N`（無 function reference） | `local N` 被選為 entry → BFS 異常 | 產出特化錯誤 `Only local symbols found`，exit code 2 |
| `--no-default-excludes` + 上述兩情境 | 同上 | 同上（entry point 過濾不受影響） |
| def 行（`def foo():` 等） | 正常選取 function definition | 行為不變 |

### 8.4 與 `--no-default-excludes` 的語義切分

| 機制 | 控制對象 | 受 `--no-default-excludes` 影響 |
|------|---------|:----:|
| Entry point 過濾 | `locate_entry_symbol()` 中的 `is_local_symbol()` 前置檢查 | ✗ |
| BFS 過濾 | `SymbolFilter` 的 `--exclude-patterns "local *"` 預設規則 | ✓ |

**原因**：Entry point 定位與 BFS 過濾的語義不同——entry point 需要一個可展開的 function-like symbol 作為 BFS 起點，local variable 無法作為有意義的起點（無呼叫關係可追蹤）。即使 BFS 允許 local symbols 通過（`--no-default-excludes`），entry point 仍應排除它們。關聯情境：情境 1（entry point 定位）、情境 10（過濾控制語義獨立性驗證）。
