# Exit Code 參考

## scip-extract

| Exit Code | 意義 | 建議處理 |
|-----------|------|----------|
| 0 | 成功 | 可直接使用輸出的 `context.md` / graph JSON |
| 1 | 擷取成功但有 broken links（引用到 SCIP 索引外的符號） | 結果可用但不完整；必要時重建 index、安裝缺少依賴或放寬模組邊界 |
| 2 | SCIP 載入或進入點定位失敗 | 檢查 `--scip-file`、entry file / line、索引是否涵蓋目標檔案 |
| 3 | 路徑解析失敗 | 確認 `--entry-file` 存在且位於 `--project-root` 內 |

## scip-graph-merge

| Exit Code | 意義 | 建議處理 |
|-----------|------|----------|
| 0 | 成功 | 使用合併後 graph 查詢 |
| 1 | `IndexHashMismatchError`：graph 基於不同版本的 `index.scip` | 重建 index 後重新擷取所有 graph，再合併 |
| 2 | 其他錯誤（檔案讀取失敗等） | 檢查 input paths 與 JSON 格式 |

## scip-graph-query

| Exit Code | 意義 | 建議處理 |
|-----------|------|----------|
| 0 | 成功；即使有 warnings 也可能是 0 | 讀 stdout 結果與 stderr warnings |
| 2 | graph 載入失敗或 node key 無匹配 | 檢查 `--graph`；先用 `--list-nodes` 找正確 key / glob |

## 常見 warnings

| Warning | 意義 | 建議處理 |
|---------|------|----------|
| `no_test_nodes_in_graph` | `--test-impact` 查不到測試節點，且 graph 中沒有 `is_test=true` 節點 | 用 `--test-file-pattern` 批次擷取測試 graph，merge 後重查 |
| `target_is_not_test_function` | `--coverage` target 不是測試函式 | 改用測試函式作 target；若要完整下游，使用 `--forward-from` |
| `result truncated at max_depth=N` | graph-query traversal 被 `--max-depth` 截斷 | 提高 `--max-depth` 或查 `truncated_branches` 指定分支 |
