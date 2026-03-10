---
name: bfs-skill
description: >
  基於 SCIP 靜態分析索引的語意級代碼探索與追蹤。
  當用戶需要追蹤呼叫鏈（「A 呼叫了什麼」「誰呼叫了 B」）、
  分析修改影響（「改了 X 哪些測試會 break」）、
  檢查測試覆蓋（「這個測試覆蓋了哪些 production code」）、
  取得跨檔案完整代碼上下文以理解模組架構或指導 subagent 時使用。
  即使用戶只是說「幫我看看這個函式」或「這個改動影響什麼」或「幫我做 code review」，
  只要涉及跨檔案的代碼追蹤或語意分析，都應該使用此 skill 而非 grep/view。
  前提：專案根目錄需存在 index.scip 且 SCIP CLI 工具可用。
---

# BFS Code Tracing Skill

基於 SCIP 靜態分析索引的語意級代碼探索與追蹤。與 grep/view 的逐層搜尋不同，此 Skill 能一次呼叫就取得完整的跨檔案呼叫圖，精確識別語意上的呼叫關係（不只是文字匹配），並支援影響分析和測試覆蓋查詢——這些都是 grep/view 做不到的。

## 前提條件

- 已安裝對應語言的 SCIP indexer，每次使用前先重建 `index.scip` 以確保與當前代碼一致（各語言安裝指引見 `references/indexer-setup.md`）
- 已安裝 `scip-extract`、`scip-graph-merge`、`scip-graph-query` CLI 工具：
  ```bash
  which scip-extract || {
    git clone git@github.com:NeoJay0705/scip-extractor.git /tmp/scip-extractor
    pip install -e /tmp/scip-extractor
  }
  ```

若上述工具未安裝，請先要求使用者安裝後再繼續，不要 fallback 至 grep/view——因為 grep 只能做文字匹配，無法提供語意正確的呼叫關係。

---

## 場景範例

以下是常見的用戶需求及對應的操作方式，幫助判斷何時及如何使用此 Skill：

| 用戶說的話 | 該怎麼做 |
|-----------|---------|
| 「幫我看看這個函式被哪些地方呼叫」 | Step 1 定位 → Step 2 擷取 → Step 3 `--reverse-from` |
| 「我改了 handler，哪些測試會受影響？」 | Step 2 擷取（含測試） → Step 3 `--test-impact` |
| 「這個測試覆蓋了哪些 production code？」 | Step 2 從測試函式擷取 → Step 3 `--coverage` |
| 「幫我理解 auth 模組的架構」 | Step 1 找模組入口 → Step 2 `--max-nodes 50` 概覽 |
| 「我想重構 check_rate，幫我看影響範圍」 | Step 3 `--reverse-from` 找呼叫者 + `--test-impact` 找受影響測試 |
| 「幫我做 code review，看改動影響」 | Step 2 擷取改動函式 → Step 3 `--reverse-from` + `--test-impact` |
| 「這段代碼的上下游關係是什麼？」 | Step 2 擷取 → Step 3 `--forward-from` + `--reverse-from` |

---

## 核心流程

### Step 0：建立 SCIP 索引

每次代碼變更後重新建索引，確保分析結果與當前代碼一致。各語言的 indexer 安裝和使用指引見 `references/indexer-setup.md`。

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
   - `is_truncated: true` → 結果不完整（見下方處理策略）
   - `collected_nodes: 1` → BFS 未展開，檢查行號是否正確
2. **讀 `## Summary` 區段**（frontmatter 之後、Layer 0 之前）：快速掌握整體結構——
   - **Modules**：涉及的模組列表及各模組節點數
   - **Layer Distribution**：各 Layer 的節點數分佈（如 `Layer 0: 1, Layer 1: 11, Layer 2: 24`）
   - **Truncated Branches**（僅 `is_truncated: true` 時出現）：被截斷的 pending symbols 列表（最多 10 個），用於判斷哪些分支值得深入
3. **驗證 Layer 0 的符號名稱**：確認 `## Layer 0` section 的 header 是預期的函式名（如 `main().`）。
   若出現 `local N` 或非預期的符號，表示進入點定位錯誤——將行號調整至 `def` 定義行重試。

**`is_truncated: true` 處理策略：**
- 若 `collected_nodes` ≤ 30 且 truncated：直接增大 `--max-nodes` 至 50-100
- 若 `collected_nodes` > 50 且 truncated：context.md 已很大（數千行），**不建議直接增大 max-nodes**。
  改用漸進式探索：查看 Summary 的 **Truncated Branches** 列表，以其中的關鍵函式為新進入點，分段擷取後用 `scip-graph-merge` 合併。

**閱讀大型 context.md 的策略：**
context.md 可能數千行（95 nodes ≈ 4800 行）。不要一次讀取整個檔案：
1. **先讀 frontmatter**：確認 `collected_nodes`、`is_truncated` 狀態
2. **讀 Summary 區段**：快速掌握模組分佈、Layer 結構、截斷分支（取代逐一 grep headers）
3. **用 graph-query 做結構化查詢**：`--forward-from` / `--reverse-from` 精準追蹤特定分支，加 `--with-source --project-root .` 直接取得源碼（最推薦）
4. **用 `--output-symbol-prefix` 過濾輸出**：若只關注特定子模組，加入 `--output-symbol-prefix "module_a/submodule"` 僅輸出 descriptor 以該前綴開頭的節點（適用於單一 SCIP package 的專案）
5. **用 `--output-modules` 過濾輸出**：若專案含多個 SCIP package，加入 `--output-modules "target_module"` 僅輸出該 package 的 Markdown。⚠️ 對單一 SCIP package 的專案（多數 Python 專案），此參數無法做子模組過濾——所有代碼歸屬同一 package name，過濾結果為「全有或全無」，改用 `--output-symbol-prefix`
6. **按需 view 特定節點**：根據 graph-query 結果只讀需要的函式代碼

### Step 3：查詢呼叫圖

在已擷取的 graph 上做結構化分析（五種模式互斥）：

> ⚠️ Node key 包含模組前綴（如 `` `scip_deep_context.cli`/main(). ``），不是短名稱。
> **先用 `--list-nodes` 查看所有可用的 key**，再用 glob pattern 匹配查詢。

| 查詢類型 | 指令 | 用途 |
|---------|------|------|
| 列出節點 | `--list-nodes` | 查看所有可查詢的 symbol key（**建議先執行**） |
| 正向追蹤 | `--forward-from '*symbol().'` | 函式呼叫了哪些函式 |
| 反向追蹤 | `--reverse-from '*symbol().'` | 誰呼叫了這個函式 |
| 測試影響 | `--test-impact '*symbol().'` | 改了 X，哪些測試 break |
| 測試覆蓋 | `--coverage '*TestClass#test().'` | 測試覆蓋了哪些 production code |

> ⚠️ **測試相關查詢前提**：`--test-impact` 和 `--coverage` 要求 graph 中包含測試節點（`is_test=true`）。若 graph 僅從 production code 入口擷取（如 `main()`），需另行從測試檔案擷取 graph 並用 `scip-graph-merge` 合併後使用。

> ⚠️ **`--coverage` 非測試目標警告**：`--coverage` 應以測試函式為目標。對 production 函式使用時，結果退化為等同 `--forward-from`（返回所有可達節點），不具「覆蓋」語義，且會觸發 `warnings: ["target_is_not_test_function"]` + stderr 警告。

```bash
# 先查看所有 node key
scip-graph-query --graph graph.json --list-nodes

# 例：反向追蹤 — 誰呼叫了 traverse()（用 glob 匹配）
scip-graph-query \
  --graph graph.json \
  --reverse-from '*traverse().'

# 例：正向追蹤 depth 1（用 glob 匹配）
scip-graph-query \
  --graph graph.json \
  --forward-from '*cli*/main().' \
  --max-depth 1
```

**附帶源碼查詢（`--with-source`）：**

預設 graph-query 輸出 JSON metadata（file、lines、layer），不含源碼。加上 `--with-source` 可直接取得 Markdown 格式的源碼上下文，省去逐一 `view` 每個檔案的步驟：

```bash
# 反向追蹤並附帶源碼（輸出 Markdown 而非 JSON）
scip-graph-query \
  --graph graph.json \
  --reverse-from '*traverse().' \
  --with-source --project-root .
```

> `--with-source` 會將輸出從 JSON 切換為 Markdown（含 YAML frontmatter + 各節點源碼）。
> 必須搭配 `--project-root` 指定專案根目錄，用於定位源碼檔案。
> 與 `--list-nodes` 互斥（list-nodes 只列出 key，不需要源碼）。

**截斷分支資訊（`truncated_branches`）：**

graph-query 的 JSON 輸出在截斷時包含 `truncated_branches` 陣列，列出被 `max_depth` 截斷的 pending node keys。此陣列與 context.md Summary 區段的 "Truncated Branches" 語義類似但獨立計算——前者基於 graph-query 的 `--max-depth` 截斷，後者基於 scip-extract 的 `--max-nodes` / `--timeout` 截斷。

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
| 查詢結果同時要看源碼 | **scip-graph-query --with-source** |
| 只看特定子模組的上下文（單 package 專案） | **scip-extract --output-symbol-prefix** |
| 只看特定 SCIP package 的上下文（多 package 專案） | **scip-extract --output-modules** |
| 搜尋字串 / config / log | grep |
| 讀取已知路徑 | view |
| 目錄結構 | glob |
| `index.scip` 不存在 | grep/view（建議使用者建索引） |

> ⚠️ `--test-impact` 和 `--coverage` 要求 graph 中包含測試節點（`is_test=true`）。若 graph 僅從 production code 入口擷取（如 `main()`），需另行從測試檔案擷取 graph 並用 `scip-graph-merge` 合併後使用。`--coverage` 應以測試函式為目標；對 production 函式使用時，結果退化為等同 `--forward-from` 並觸發 `target_is_not_test_function` warning（見 Step 3）。

## 故障排除

| 問題 | 處理 |
|------|------|
| `index.scip` 不存在或過時 | 執行 Step 0 重建索引（每次使用前都應重建） |
| `collected_nodes: 1` | 行號未指向函式定義行，調整後重試 |
| `is_truncated: true` | 查看 Summary 的 Truncated Branches，以關鍵分支為新進入點分段擷取；或增大 `--max-nodes` |
| 合併報 IndexHashMismatchError | 重建索引後需重新擷取所有 graph |
| context.md 太大、只需特定子模組 | 加 `--output-symbol-prefix "submodule"` 按 descriptor prefix 過濾（單 package 專案適用）；或 `--output-modules "module_name"` 按 SCIP package 過濾（多 package 專案適用） |

### Exit Code 參考

詳見 `references/exit-codes.md`。常見的非零 exit code：
- **scip-extract exit 1**：有 broken links，結果可用但不完整
- **scip-extract exit 2**：SCIP 載入或進入點定位失敗
- **scip-graph-merge exit 1**：graph 基於不同版本的 index.scip

## 進階參數

完整的進階參數文件見 `references/advanced-params.md`。以下為最常用的幾個：

- **`--output-symbol-prefix "submodule"`**：僅輸出指定 descriptor 前綴的節點（單 SCIP package 專案的子模組過濾）
- **`--output-modules "module_name"`**：僅輸出指定 SCIP package 的 Markdown（多 package 專案適用）
- **`--include-fields`**：BFS 包含 field/property symbols
- **`--with-source --project-root .`**：graph-query 輸出 Markdown 附帶源碼（取代逐一 view）

> **`--project-modules` vs `--output-modules` vs `--output-symbol-prefix`**：`--project-modules` 控制 BFS 展開邊界；`--output-modules` 控制輸出的 SCIP package 過濾；`--output-symbol-prefix` 控制輸出的 descriptor prefix 過濾。三者可獨立或組合使用。
