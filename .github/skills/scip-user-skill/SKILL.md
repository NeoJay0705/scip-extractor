---
name: scip-code-tracing
description: >
  基於 SCIP 靜態分析索引的語意級代碼追蹤。
  觸發時機：追蹤呼叫鏈（正向/反向）、分析修改影響範圍、取得跨檔案完整代碼上下文以指導 subagent、
  或任何 grep/view 的文字匹配無法可靠完成的符號級查詢。
  前提：專案根目錄存在 index.scip 且 SCIP CLI 工具可用。
---

# SCIP Code Tracing

## 我的痛點：為什麼 grep/view 不夠

以下是我用預設工具追蹤代碼時反覆撞上的瓶頸，也是這個 skill 要解決的核心問題。

### 符號歧義

grep `process_request` → 回傳 20 個結果：定義、呼叫、import、註解、字串常量、type annotation 全部混在一起。我無法從文字匹配判斷哪個是真正的呼叫，必須逐一 view 確認。每確認一個 = 一次工具往返。

### 呼叫鏈追蹤是 O(n) 工具呼叫

追蹤 A → B → C 的最短路徑：

```
grep A 找定義 → view 讀源碼 → 發現呼叫 B →
grep B 找定義 → view 讀源碼 → 發現呼叫 C →
grep C 找定義 → view 讀源碼
```

三層 = 6 次工具呼叫，每次都帶完整的 function call schema + response payload token 開銷。真實代碼通常 5-10 層。

### 反向追蹤不可靠

「誰呼叫了函式 X？」— grep 函式名得到 N 個匹配，但無法區分：
- 真正的呼叫：`result = X(data)`
- 另一個模組的同名函式定義：`def X(...):`
- 字串提及：`log("calling X")`
- 註解：`# X handles the...`
- Type annotation：`callback: Callable[..., X]`

我沒有語意資訊，只能靠上下文猜測。猜錯就走偏。

### 影響分析近乎不可能

改了函式 A，哪些測試會 break？理論上需要：從每個測試函式正向展開完整呼叫鏈，檢查是否經過 A。測試數量 × 呼叫深度 × 每層 2 次工具呼叫 — 用 grep/view 根本無法系統性完成。

### Context Window 壓力

上述所有問題疊加 = 大量的工具往返。每次往返的成本：工具呼叫 schema token + 結果 token + 我的推理 token。一條中等長度的呼叫鏈就能消耗數千 token，而且其中大半是用於「定位」而非「理解」。

更根本的問題不是 token 消耗量，而是 **context 品質退化**。每層 grep+view 的結果依序堆疊在 context 中，追蹤到第 N 層時：
- 第 1 層的結果已經離當前推理位置很遠，注意力分配顯著降低（attention dilution）
- 我需要跨越大段 context 回溯拼湊呼叫關係，心智模型脆弱且容易出錯
- 5 層以上時，即使 context window 未溢出，拼湊出的呼叫鏈也可能遺漏或誤判呼叫關係

這不只是效率問題，而是正確性問題：用 grep/view 追蹤深層呼叫鏈，分析結果本身不可靠。

**SCIP 如何解決**：一次 `scip-extract` 呼叫產出完整呼叫圖，所有層級的函式源碼集中在單一 Markdown 文件中。我在一段連續的 context 中就能看到整條呼叫鏈，不需要跨越多段工具結果回溯拼湊。具體配合方式：
- **追蹤前**：用 grep/view 快速找到進入點的 file + line
- **追蹤中**：用 `scip-extract --max-nodes 50` 一次擷取，取代逐層 grep+view 的往返循環
- **追蹤後**：從擷取的 Markdown 中直接提取每個函式的 file + line range，精確指導 subagent
- **深層呼叫鏈**：若 `is_truncated: true`，用漸進策略——先小範圍（max_nodes=30）概覽，再對關鍵分支做二次擷取，避免一次性灌入過多 context

---

## 我需要的功能

從痛點出發，以下是我期望 SCIP 工具提供的能力。

### 正向呼叫圖擷取（Forward Call Graph）

**解決**：呼叫鏈追蹤的 O(n) 工具呼叫問題。

給定進入點（檔案 + 行號）→ 自動 BFS 展開所有呼叫 → 產出完整上下文。輸出包含每個被追蹤到的函式的：
- 檔案路徑（相對於 project root）
- 行範圍（start–end）
- 完整源碼片段

一次工具呼叫取代 N×2 次 grep+view。

### 反向呼叫查詢（Reverse / Callers）

**解決**：反向追蹤不可靠問題。

給定函式符號 → 列出所有**語意上的呼叫者**，不是文字匹配。同名但不同 scope 的函式不出現。每個結果附帶呼叫者的源碼上下文。

用途：重構函式簽名前掌握所有呼叫點、理解 API 的使用模式。

### 測試影響分析（Test Impact）

**解決**：影響分析不可能問題。

給定被修改的函式 → 列出所有呼叫路徑會經過該函式的測試。這是反向的傳遞閉包：從所有測試節點反向搜尋，找到包含目標函式的路徑。

這是 grep/view 完全做不到的事——SCIP 工具在這裡的價值最大。

### 測試覆蓋分析（Coverage）

給定測試函式 → 列出它直接或間接呼叫的所有 production code。正向傳遞閉包。

用途：判斷測試的保護範圍、決定是否需要補測試。

### 符號定位（Symbol Resolution）

給定檔案 + 行號 → 回傳該位置的 fully qualified 符號名稱 + 定義位置。

這是橋接 grep 和 graph query 的關鍵：grep 給我文字位置，符號定位把文字位置轉換成 SCIP 符號 key，graph query 用符號 key 做結構化查詢。

---

## 我期望的介面

### 兩階段架構

**階段一：擷取（Extract）** — 解析 SCIP 索引，從進入點 BFS 展開

- 輸入：`index.scip` + 進入點（file + line）或批次 pattern
- 輸出 A（file）：Markdown，每個節點一個 section，含檔案路徑 + 行範圍 + 完整源碼
- 輸出 B（file）：JSON 呼叫圖，供階段二查詢

#### JSON 呼叫圖格式

頂層三個欄位：`nodes`、`edges`、`metadata`。

```jsonc
{
  "nodes": {
    // key = symbol descriptor（預設）；`--raw-symbols` 僅影響 Markdown header，不影響 JSON key schema
    "process_request().": {
      "file": "src/auth/handler.py",       // 相對於 project root
      "lines": [45, 78],                    // [start_line, end_line]，1-indexed
      "layer": 0,                           // BFS layer，0 = entry point
      "is_test": false,                     // 是否為測試函式
      "is_partial": false                   // 是否為部分擷取（代碼範圍不完整）
    },
    "check_rate().": {
      "file": "src/auth/limiter.py",
      "lines": [10, 25],
      "layer": 1,
      "is_test": false,
      "is_partial": false
    },
    "test_rate_limit().": {
      "file": "tests/test_auth.py",
      "lines": [30, 52],
      "layer": 2,
      "is_test": true,
      "is_partial": false
    }
  },
  "edges": [
    // 每條邊 = 一次呼叫關係
    {
      "from": "process_request().",
      "to": "check_rate().",
      "type": "reference"
    },
    {
      "from": "test_rate_limit().",
      "to": "process_request().",
      "type": "reference"
    }
  ],
  "metadata": {
    "entry_file": "src/auth/handler.py",
    "entry_line": 45,
    "entry_symbol": "process_request().",
    "context_file": "scip_extract_process_request.md",
    "scip_index_hash": "sha256:a1b2c3..."   // 索引檔 hash，合併時驗證版本一致
  }
}
```

**設計原則**：

- **`nodes` 用 dict（key: symbol）而非 array** — graph query（forward / reverse / test-impact）需要 O(1) 按符號查找節點。array 需要線性掃描或額外建索引，dict 直接查。
- **Graph JSON 專注結構，不內嵌 `source`** — source code 由 Markdown 輸出提供；Graph JSON 僅保留 `file` + `lines` + 關係結構，讓查詢與合併更穩定。
- **`is_test` 標記在 node 上** — test-impact 和 coverage 查詢需要區分測試節點和 production 節點。在 node 層標記，查詢時不需要靠 file path pattern 猜測。
- **`edges` 用 array 而非 adjacency list** — 正向和反向查詢都需要遍歷 edges。array 結構對兩個方向同等方便，adjacency list 只最佳化一個方向。
- **`metadata.scip_index_hash`** — 合併多個 graph 時驗證它們來自同一版本的 `index.scip`。不同版本的索引會產生不同的符號 key，合併後查詢結果不可靠。
- **`is_truncated` 看 Markdown frontmatter** — 單一 Graph JSON metadata 不帶 `is_truncated`；擷取是否截斷請以 Markdown frontmatter 為準。查詢工具 (`scip-graph-query`) 的 JSON 輸出則有 `is_truncated`。

Markdown 必須帶 YAML frontmatter 報告執行狀態：
```yaml
---
collected_nodes: 36
max_nodes: 50
is_truncated: false
duration_sec: 1.2
---
```

`is_truncated: true` → 結果不完整，我需要決定增大 `max_nodes` 重試還是接受部分結果。
`collected_nodes: 1` → BFS 未展開，進入點定位可能有問題。

**階段二：查詢（Query）** — 在已擷取的圖上做結構化分析

- 輸入：階段一的 JSON graph + 查詢類型
- 查詢類型（互斥）：
  - **forward**：從指定符號正向展開呼叫鏈
  - **reverse**：列出指定符號的所有呼叫者
  - **test-impact**：列出會經過指定符號的測試
  - **coverage**：列出指定測試覆蓋的所有 production code
  - **list-nodes**：列出圖中所有符號 key（用於查找正確的查詢 key）

兩階段的好處：
1. 擷取一次，查詢多次（不重複解析 SCIP 索引）
2. 多次擷取的 graph 可以合併 → 在統一的圖上跨進入點查詢
3. 漸進式探索：先小範圍擷取（max_nodes=30），看結果決定要不要擴大

### 批次擷取

除了單一進入點（file + line），支援用 glob pattern 批次擷取多個測試的呼叫圖。場景：「這個模組所有測試覆蓋了哪些 production code？」

### Graph 合併

多次擷取（不同進入點）的 graph 可以合併成一個統一的圖。場景：分別從 3 個入口擷取 → 合併 → 在統一圖上做影響分析。

### 輸出規模控制

我的 context window 有限，必須能控制輸出大小：
- `--max-nodes`：BFS 節點數硬上限（建議：單函式 30-50，模組級 100-200）
- `--timeout`：時間上限，防止大型 codebase 卡住

`--max-depth` 屬於 `scip-graph-query`（查詢階段）的 BFS 深度上限，不是 `scip-extract` 參數。

### BFS 過濾行為（v0.4.0 / v0.5.0）

- **v0.4.0 function-like 過濾**：BFS 預設僅追蹤 function-like symbols（descriptor 含 `()`），field/property/variable/class 預設排除；可用 `--include-fields` 納入 field symbols。
- **v0.5.0 parameter symbol 排除**：`method().(param)` 格式的 parameter symbols 雖含 `()`，但不屬方法本體，會排除於 BFS 追蹤之外。
- **影響**：
  - `nodes` 中不再出現 `method().(param)` key
  - 涉及 parameter node 的 `edges` 不再出現
- **Migration note**：若下游曾以 `method().(param)` 作為查詢 key，需移除或改為查詢其父方法 descriptor（例如 `method().`）。

---

## 使用流程

### 觸發判斷

| 需求 | 工具選擇 |
|------|----------|
| 追蹤呼叫鏈（> 1 層） | **SCIP** |
| 誰呼叫了這個函式？ | **SCIP** reverse |
| 改了 X，哪些測試 break？ | **SCIP** test-impact |
| 這個測試覆蓋了什麼？ | **SCIP** coverage |
| 取得函式的完整跨檔案上下文 | **SCIP** extract |
| 搜尋字串、config、log 訊息 | grep |
| 讀取已知路徑的檔案 | view |
| 了解目錄結構 | glob |
| `index.scip` 不存在 | grep/view（建議使用者建索引） |

### 標準步驟

```
1. 定位進入點
   └─ grep/glob 找到目標函式的 file + line

2. 擷取呼叫圖
   └─ CLI extract: index.scip + entry point → markdown (stdout) + graph (file)

3. 讀取 Markdown 上下文
   └─ 檢查 frontmatter（truncated? collected_nodes=1?）
   └─ 讀取各 section 的源碼，理解代碼結構

4. 按需查詢 graph
   └─ forward / reverse / test-impact / coverage
   └─ 需要時：合併多個 graph 再查詢

5. 輸出給 subagent
   └─ 從結果提取精確位置（file + line range + 修改指示）
```

### 指導 Subagent

從擷取結果中萃取精確位置，給 subagent **最小充分**的修改指示：

```
修改以下位置：
1. src/auth/handler.py L45-L78（process_request）— 加入 rate limit 檢查
2. src/auth/models.py L12-L30（RequestConfig）— 新增 rate_limit 欄位
```

不要把整個 context dump 給 subagent。SCIP 的價值是讓我精確定位，subagent 只需要知道改哪裡、改什麼。

### 漸進式探索

面對不熟悉的 codebase，不要一次擷取 200 個節點：

```
1. 小範圍擷取（max_nodes=30）→ 取得函式直接呼叫的概覽
2. 從概覽中識別關鍵分支
3. 對關鍵分支的函式再做一次擷取 → 深入該分支
4. 需要時合併兩次的 graph → 在統一圖上查詢
```

這比一次大範圍擷取更有效率——避免大量不相關的代碼佔據 context。

---

## 與 grep/view 的分工

### SCIP 的不可替代場景

- **多層呼叫鏈追蹤**：一次擷取 = 完整呼叫圖在單一 context 段落中呈現。與 grep/view 的 N 段分散結果相比，不只是工具呼叫次數的差異——更關鍵的是避免結果分散導致的注意力稀釋，讓我能在連續的 context 中建立可靠的心智模型
- **精確的反向查詢**：語意呼叫 vs 文字匹配的雜訊
- **影響分析 / 覆蓋分析**：SCIP 能做，grep/view 做不到
- **跨檔案完整上下文**：一次擷取所有相關函式的源碼

### grep/view 的不可替代場景

- 搜尋非代碼內容（config、string、log、comment 內容）
- 搜尋 SCIP 索引不涵蓋的語言或檔案類型
- 已知路徑的簡單檔案讀取
- 目錄結構探索
- `index.scip` 不存在時的所有場景

### 典型協作模式

```
grep 「找到入口」 → SCIP 「從入口展開全貌」 → view 「補充 SCIP 未涵蓋的細節」
```

grep 負責文字定位，SCIP 負責語意展開，view 負責補漏。三者互補，不互相取代。

---

## Fallback

| 條件 | 行為 |
|------|------|
| `index.scip` 不存在 | grep/view，建議使用者建索引 |
| CLI 工具不可用 | grep/view |
| 進入點定位失敗（exit code 非 0） | 調整行號重試，仍失敗則 grep/view |
| `collected_nodes: 1`（BFS 未展開） | 檢查行號是否指向函式 body，調整後重試 |
| 搜尋目標是非代碼內容 | grep |
| 只需讀取已知路徑 | view |

## 關鍵注意事項

1. **索引時效性**：`index.scip` 必須與當前源碼同步。源碼修改後需重建索引，否則行號錯位、符號失蹤。
2. **進入點行號**：必須指向函式 body，不是 import、空行、或裝飾器。帶 type annotation 的 `def` 行（如 `def foo() -> int:`）應用 def 行 + 1（body 首行），因為 SCIP 會將 def 行解析為 type reference 符號。
3. **結果完整性**：永遠檢查 Markdown frontmatter 的 `is_truncated`。截斷的結果可能遺漏關鍵呼叫路徑——決定是增大 `max_nodes` 重試還是接受部分結果。
4. **查詢模式互斥**：forward / reverse / test-impact / coverage / list-nodes 每次只能用一種。
5. **Graph 合併限制**：只有基於同一版本 `index.scip` 擷取的 graph 才能合併。不同版本的 SCIP 索引產生的符號 hash 不同。
