# 故障排除

| 問題 | 常見原因 | 處理 |
|------|----------|------|
| `index.scip` 不存在或過時 | 尚未建索引、切分支後未重建、代碼剛修改 | 依 `references/indexer-setup.md` 重建索引；重建後重新擷取 graph |
| 找不到 `scip-extract` / `scip-graph-query` | CLI 尚未安裝或 venv 未啟動 | 依 `references/indexer-setup.md` 安裝 `scip-extractor`，確認 `which scip-extract` |
| `No reference found` / 進入點定位失敗 | 行號不是函式定義行、檔案路徑不在 project root、索引不含該檔 | 用 anchored rg 重新找 definition line；確認 `--project-root` 與 `--entry-file`；重建 index |
| `collected_nodes: 1` | 行號命中 local symbol、函式無可解析呼叫、排除規則過嚴、index 不完整、field/property 被排除 | 檢查 Layer 0；放寬 `--project-modules` / `--exclude-patterns`；重建 index；必要時加 `--include-fields` |
| `is_truncated: true` | `--max-nodes` 或 `--timeout` 截斷 | 見 `references/large-context-strategy.md`；小圖可增大限制，大圖應依 Truncated Branches 分段探索 |
| context 太大 | 入口太高階、max-nodes 太大、模組範圍太廣 | 先用 `--max-nodes 30` 概覽；使用 `--output-symbol-prefix` 或 `--output-modules` 聚焦輸出；用 graph-query 查特定分支 |
| `--output-modules` 沒有縮小 Python 子模組輸出 | 多數 Python 專案只有單一 SCIP package name | 詳見 `references/advanced-params.md` |
| `--test-impact` / `--coverage` 警告 | warning 詳細處理 | 詳見 `references/exit-codes.md`「常見 warnings」 |
| `scip-graph-merge` 報 `IndexHashMismatchError` | graph 來自不同版本的 `index.scip` | 重建 index 後，重新擷取所有要合併的 graph |
| `--with-source` 報錯 | 未提供 `--project-root` 或 source path 無法解析 | 加 `--project-root .`；確認 graph 的檔案路徑仍存在 |
| glob pattern 匹配多個 node | pattern 太寬，CLI 會使用排序後第一個並在 stderr 列出 matches | 先 `--list-nodes`，改用更精準 pattern |
| 查詢結果被 `max_depth` 截斷 | graph-query 預設 `--max-depth 10` | 增加 `--max-depth`，或針對 `truncated_branches` 做局部查詢 |

## Fallback 說法

若無法建立索引或 CLI 不可用，可以 best-effort 使用 grep/view，但回覆必須明示限制：

> 目前沒有可用 SCIP 索引，以下只能做文字匹配與局部閱讀；無法保證語意呼叫追蹤、測試影響或完整 blast radius 正確。
