---
name: bfs-skill
description: >
  基於 SCIP 靜態分析索引的語意級代碼探索與追蹤。Use for semantic code tracing when users ask about callers, callees, usages, call graph, dependency graph, impact analysis, blast radius, test impact, test coverage, refactor safely, dead code, 上游、下游、連動、誰用了、死代碼。適用於追蹤呼叫鏈（A 呼叫了什麼、誰呼叫了 B）、分析修改影響、檢查測試覆蓋、取得跨檔案完整上下文；code review 僅在需要 impact-aware / semantic impact review 時使用。前提：專案根目錄需存在 index.scip 且 SCIP CLI 工具可用；不可用時可 best-effort grep/view，但必須明示無法做語意呼叫追蹤或完整影響分析。
---

# BFS Code Tracing Skill

基於 SCIP 靜態分析索引做語意級代碼探索與追蹤；能取得跨檔案呼叫圖、影響分析、測試影響與測試覆蓋，避免只靠 grep/view 的文字匹配。

## 場景範例

| 用戶說的話 | 該怎麼做 |
|-----------|---------|
| 「誰呼叫了這個函式 / callers / 誰用了」 | Step 1 → Step 2 → `--reverse-from` |
| 「A 呼叫了什麼 / callees / 下游」 | Step 1 → Step 2 → `--forward-from` |
| 「改了 handler，哪些測試會受影響？」 | production + tests graph merge → `--test-impact` |
| 「這個測試覆蓋了哪些 production code？」 | production + tests graph merge → `--coverage` |
| 「理解模組架構 / dependency graph」 | 找入口 → 小圖概覽 → 必要時分段合併 |
| 「refactor safely / blast radius / code review 看影響」 | impact-aware review：反向追蹤 + 測試影響 |
| 「找死代碼」 | `--reverse-from`；無 callers 時再補查動態入口 |

## 前提條件與 fallback policy

- 每次使用前先重建或確認 `index.scip` 與當前代碼一致；安裝與建索引見 `references/indexer-setup.md`。
- 需可執行 `scip-extract`、`scip-graph-merge`、`scip-graph-query`。
- 若 `index.scip` 或工具不可用，**優先要求建立索引 / 安裝工具**；若只能 best-effort grep/view，必須明示：「目前沒有可用 SCIP 索引，無法提供語意正確的呼叫追蹤、測試影響或完整 blast radius；以下僅為文字匹配推測。」

---

## 核心流程

### Step 0：建立 SCIP 索引

每次代碼變更後重新建索引，確保分析結果與當前代碼一致。詳見 `references/indexer-setup.md`。

### Step 1：定位進入點

用 grep/glob 找到目標函式的**檔案路徑**與**行號**：

```bash
rg -n '^\s*def process_request\b' src/
```

> 行號應指向 `def` / `func` / `function` 定義行本身，不是 body 首行、import、空行或裝飾器；否則可能命中 `local N` 等局部符號。

### Step 2：擷取呼叫圖

```bash
scip-extract --scip-file index.scip --project-root . \
  --entry-file src/auth/handler.py --entry-line 46 \
  --max-nodes 50 --timeout 10 --graph-output graph.json > context.md
```

| 參數 | 說明 |
|------|------|
| `--max-nodes` | BFS 節點上限；單函式 30-50，模組級 100-200 |
| `--timeout` | 時間上限（秒） |
| `--graph-output` | 輸出 JSON 呼叫圖供查詢 / 合併 |

**檢查結果：**
1. frontmatter：`is_truncated: true` 表示不完整；策略見 `references/large-context-strategy.md`。
2. `collected_nodes: 1` 多原因 checklist：行號是否指向 definition；目標是否無可解析 outgoing references；`--project-modules` / `--exclude-patterns` 是否過嚴；`index.scip` 是否過時或缺依賴；是否需要 `--include-fields` 追蹤 field/property。
3. `## Summary`：看 Modules、Layer Distribution、Truncated Branches。
4. `## Layer 0`：確認 header 是預期函式；若是 `local N` 或非預期符號，調整行號重試。

### Step 3：查詢呼叫圖

查詢模式互斥；`--max-depth` 預設 `10`。Node key 含模組前綴（如 `` `scip_deep_context.cli`/main(). ``），先用 `--list-nodes` 查看 key，再用 glob pattern。

| 查詢類型 | 指令 | 用途 |
|---------|------|------|
| 列出節點 | `--list-nodes` | 查看所有 symbol key |
| 正向追蹤 | `--forward-from '*symbol().'` | callees / 下游 |
| 反向追蹤 | `--reverse-from '*symbol().'` | callers / 上游 |
| 測試影響 | `--test-impact '*symbol().'` | 改了 X，哪些測試可能 break |
| 測試覆蓋 | `--coverage '*TestClass#test().'` | 測試 forward traversal 後過濾 `is_test=false` production 節點 |

```bash
scip-graph-query --graph graph.json --list-nodes
scip-graph-query --graph graph.json --reverse-from '*traverse().'
scip-graph-query --graph graph.json --forward-from '*cli*/main().' --max-depth 1
```

**`--coverage` 語義：** target 應為測試函式；實作會先做 forward traversal，再只保留 `is_test=false` 節點。若 target 不是測試函式，會觸發 `target_is_not_test_function` warning。若要完整 forward set（含測試與非測試節點），請用 `--forward-from`。

**測試影響 / 覆蓋標準 4 步 workflow：**

```bash
# 1) extract production
scip-extract --scip-file index.scip --project-root . --entry-file src/auth/handler.py --entry-line 46 --max-nodes 80 --graph-output prod.graph.json > prod.context.md
# 2) batch extract tests（產生 is_test=true 節點）
scip-extract --scip-file index.scip --project-root . --test-file-pattern '*test*.py' --max-nodes 80 --graph-output tests.graph.json > tests.context.md
# 3) merge
scip-graph-merge prod.graph.json tests.graph.json -o unified.graph.json
# 4) query
scip-graph-query --graph unified.graph.json --test-impact '*target().'
scip-graph-query --graph unified.graph.json --coverage '*TestClass#test_*().'
```

> `--test-impact` / `--coverage` 需要 graph 含 `is_test=true` 節點；缺少時先批次擷取再合併（warning 詳見 `references/exit-codes.md`）。

**附帶源碼：**

```bash
scip-graph-query --graph graph.json --reverse-from '*traverse().' --with-source --project-root .
```

`--with-source` 會輸出 Markdown 源碼上下文；必須搭配 `--project-root`，且與 `--list-nodes` 互斥。

### Step 4（可選）：合併多個 Graph

```bash
scip-graph-merge graph_a.json graph_b.json -o unified.json
scip-graph-query --graph unified.json --test-impact '*target().'
```

> 只有基於同一版本 `index.scip` 的 graph 才能合併；重建索引後需重新擷取所有 graph。

---

## 漸進式探索策略

1. **概覽**：`--max-nodes 30` 取得直接呼叫與主要分支。
2. **識別**：讀 Summary 的 Modules / Layer Distribution / Truncated Branches。
3. **深入**：以關鍵分支函式為新進入點再次擷取。
4. **合併**：用 `scip-graph-merge` 統一 graph 後查詢。

## References Index

- `references/indexer-setup.md`：SCIP indexer、`scip-extract` CLI 安裝與建索引。
- `references/large-context-strategy.md`：大型 `context.md` 閱讀、截斷分支、分段探索策略。
- `references/advanced-params.md`：進階參數、輸出過濾、batch test extract、graph-query 參數。
- `references/troubleshooting.md`：常見問題與處理。
- `references/exit-codes.md`：CLI exit code 對照。
