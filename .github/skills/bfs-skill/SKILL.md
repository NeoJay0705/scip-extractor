---
name: bfs-skill
description: >
  代碼檢查/追蹤. Use this when asked to explore code, trace call chains, find callers or callees,
  analyze impact of changes, check test coverage, find references, track dependencies,
  understand how a function works, follow code flow, identify usage patterns,
  or navigate cross-file relationships.
---

# BFS Code Tracing Skill

基於 SCIP 靜態分析索引的語意級代碼探索與追蹤。當需要理解代碼結構、追蹤呼叫關係、分析修改影響範圍時，使用此 skill 取代逐層 grep/view 的低效循環。

## 前提條件

- 專案根目錄存在 `index.scip`（SCIP 靜態分析索引）
- 已安裝 `scip-extract`、`scip-graph-merge`、`scip-graph-query` CLI 工具（透過 `pipx install ./scip-deep-context` 安裝）

若 `index.scip` 不存在或 CLI 不可用，fallback 至 grep/view。

---

## 核心流程

### Step 1：定位進入點

用 grep/glob 找到目標函式的**檔案路徑**與**行號**。

```bash
grep -rn "def process_request" src/
```

> ⚠️ 行號應指向 `def` / `func` / `function` 定義行本身（不是 body 首行、import、空行、裝飾器）。
> 指向 body 內部行可能命中 `local N` 等局部變數符號，導致進入點解析錯誤。

### Step 2：擷取呼叫圖

從進入點 BFS 展開，一次取得完整跨檔案上下文：

```bash
scip-extract \
  --scip-file index.scip \
  --project-root . \
  --entry-file src/auth/handler.py \
  --entry-line 46 \
  --max-nodes 50 \
  --timeout 10 \
  --graph-output graph.json \
  > context.md
```

**關鍵參數：**

| 參數 | 說明 |
|------|------|
| `--max-nodes` | BFS 節點上限（單函式 30-50，模組級 100-200） |
| `--timeout` | 時間上限（秒），防止大型 codebase 卡住 |
| `--graph-output` | 同時輸出 JSON 呼叫圖供後續查詢 |

**檢查結果：**
1. 讀取 Markdown frontmatter：
   - `is_truncated: true` → 結果不完整，考慮增大 `max_nodes`
   - `collected_nodes: 1` → BFS 未展開，檢查行號是否正確
2. **驗證 Layer 0 的符號名稱**：確認 `## Layer 0` section 的 header 是預期的函式名（如 `main().`）。
   若出現 `local N` 或非預期的符號，表示進入點定位錯誤——將行號調整至 `def` 定義行重試。

### Step 3：查詢呼叫圖

在已擷取的 graph 上做結構化分析（五種模式互斥）：

| 查詢類型 | 指令 | 用途 |
|---------|------|------|
| 正向追蹤 | `--forward-from 'symbol().'` | 函式呼叫了哪些函式 |
| 反向追蹤 | `--reverse-from 'symbol().'` | 誰呼叫了這個函式 |
| 測試影響 | `--test-impact 'symbol().'` | 改了 X，哪些測試 break |
| 測試覆蓋 | `--coverage 'TestClass#test().'` | 測試覆蓋了哪些 production code |
| 列出節點 | `--list-nodes` | 查看所有可查詢的 symbol key |

```bash
# 例：反向追蹤 — 誰呼叫了 check_rate()
scip-graph-query \
  --graph graph.json \
  --reverse-from 'check_rate().'

# 例：測試影響分析
scip-graph-query \
  --graph graph.json \
  --test-impact 'BacktestEngine#run().'
```

### Step 4（可選）：合併多個 Graph

多次擷取的 graph 可合併後做跨入口查詢：

```bash
scip-graph-merge graph_a.json graph_b.json -o unified.json
scip-graph-query --graph unified.json --test-impact 'target().'
```

> 只有基於同一版本 `index.scip` 的 graph 才能合併。

---

## 漸進式探索策略

面對不熟悉的 codebase，不要一次擷取大量節點：

1. **概覽**：`--max-nodes 30` 取得直接呼叫的函式
2. **識別**：從概覽中判斷關鍵分支
3. **深入**：以關鍵分支的函式為新進入點，再次擷取
4. **合併**：用 `scip-graph-merge` 統一兩次的 graph

---

## 工具選擇決策表

| 需求 | 工具 |
|------|------|
| 追蹤呼叫鏈（> 1 層） | **scip-extract** |
| 誰呼叫了這個函式 | **scip-graph-query --reverse-from** |
| 改了 X，哪些測試 break | **scip-graph-query --test-impact** |
| 測試覆蓋了什麼 | **scip-graph-query --coverage** |
| 跨檔案完整上下文 | **scip-extract** |
| 搜尋字串 / config / log | grep |
| 讀取已知路徑 | view |
| 目錄結構 | glob |
| `index.scip` 不存在 | grep/view（建議使用者建索引） |

## 故障排除

| 問題 | 處理 |
|------|------|
| `index.scip` 不存在 | 依語言執行對應 indexer（Python: `npx @sourcegraph/scip-python index .`） |
| exit code 2 | SCIP 載入或進入點定位失敗，調整行號 |
| `collected_nodes: 1` | 行號未指向函式 body，調整後重試 |
| `is_truncated: true` | 增大 `--max-nodes` 或分段擷取 |
| 合併報 IndexHashMismatchError | 重建索引後需重新擷取所有 graph |

## 進階參數

| 參數 | 說明 |
|------|------|
| `--include-fields` | BFS 包含 field/property symbols |
| `--no-default-excludes` | 停用預設排除（含 local variable） |
| `--exclude-patterns` | 自訂排除 pattern（逗號分隔） |
| `--project-modules` | 限制 BFS 只追蹤指定模組 |
| `--no-dedup` | 停用 containment dedup |
| `--raw-symbols` | 顯示完整 SCIP symbol |
| `--test-file-pattern` | 批次提取：匹配測試檔名（與 `--entry-file` 互斥） |
| `--test-method-pattern` | 批次提取：匹配測試方法名 |
