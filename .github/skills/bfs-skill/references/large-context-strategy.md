# 大型 context.md 閱讀與截斷分支策略

`context.md` 可能非常大（例如 95 nodes 約數千行）。不要一開始就全文讀取；先用 frontmatter、Summary 與 graph-query 取得結構，再按需讀源碼。

## 建議閱讀順序

1. **先讀 YAML frontmatter**
   - `entry_symbol`：確認進入點是否為預期函式。
   - `collected_nodes`：估計上下文規模。
   - `is_truncated`：判斷結果是否被 `--max-nodes` 或 `--timeout` 截斷。
2. **讀 `## Summary` 區段**
   - **Modules**：涉及哪些 SCIP package / module。
   - **Layer Distribution**：各 BFS layer 節點數，快速判斷展開形狀。
   - **Truncated Branches**：若有截斷，列出尚未展開的 pending symbol keys（通常最多列出前幾個），用來挑下一輪入口。
3. **用 graph-query 做結構化查詢**
   - `--forward-from`：查下游 / callees。
   - `--reverse-from`：查上游 / callers。
   - 加 `--with-source --project-root .` 可直接輸出 Markdown 源碼，減少逐檔 view。
4. **只讀必要節點**
   - 根據 query 結果中的 file / line ranges 精準 view 相關函式。
   - 避免為了找一個分支而讀完整 context。

## `is_truncated: true` 處理

- 若 `collected_nodes <= 30` 且 truncated：通常可以先把 `--max-nodes` 增至 50-100，並適度提高 `--timeout`。
- 若 `collected_nodes > 50` 且 truncated：不要盲目增大 `--max-nodes`，context 可能快速膨脹。應讀 Summary 的 **Truncated Branches**，選關鍵 pending symbols 作為新入口分段擷取。
- 分段擷取後，用 `scip-graph-merge` 合併 graph，再用 `scip-graph-query` 做跨入口查詢。

## Truncated Branches 的兩種來源

| 來源 | 截斷原因 | 使用方式 |
|------|----------|----------|
| `context.md` Summary 的 `Truncated Branches` | `scip-extract` 受 `--max-nodes` / `--timeout` 限制 | 挑選下一輪 `scip-extract` 入口，分段擷取 |
| `scip-graph-query` JSON 的 `truncated_branches` | 查詢受 `--max-depth` 限制（預設 10） | 提高 `--max-depth` 或對該分支做更聚焦查詢 |

兩者語義類似（都是尚未展開的 pending nodes），但計算階段不同：前者發生在擷取 graph 時，後者發生在查詢 graph 時。

## 輸出過濾策略

- `--output-symbol-prefix "pkg/submodule"`：依 SCIP descriptor prefix 過濾 Markdown 輸出，適合單一 SCIP package 的 Python 專案做子模組聚焦。
- `--output-modules "package_name"`：依 SCIP package name 過濾 Markdown 輸出，適合多 package / monorepo。
- 兩者都只影響 Markdown 渲染，不改變 BFS 收集與 graph-output；同時啟用時是 AND 關係。

## 推薦分段流程

```bash
# 1) 小規模概覽
scip-extract --scip-file index.scip --project-root . \
  --entry-file src/service.py --entry-line 40 \
  --max-nodes 30 --graph-output overview.graph.json > overview.md

# 2) 從 Summary 的 Truncated Branches 選關鍵符號，重新定位其 file/line 後深入
scip-extract --scip-file index.scip --project-root . \
  --entry-file src/service/deep_branch.py --entry-line 88 \
  --max-nodes 80 --graph-output branch.graph.json > branch.md

# 3) 合併後查詢
scip-graph-merge overview.graph.json branch.graph.json -o unified.graph.json
scip-graph-query --graph unified.graph.json --forward-from '*target().' --with-source --project-root .
```
