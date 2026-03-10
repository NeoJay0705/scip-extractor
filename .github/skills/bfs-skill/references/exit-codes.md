# Exit Code 參考

## scip-extract

| Exit Code | 意義 |
|-----------|------|
| 0 | 成功 |
| 1 | 擷取成功但有 broken links（引用到 SCIP 索引外的符號），結果可用但不完整 |
| 2 | SCIP 載入或進入點定位失敗 |
| 3 | 路徑解析失敗（entry file 不存在或不在 project root 內） |

## scip-graph-merge

| Exit Code | 意義 |
|-----------|------|
| 0 | 成功 |
| 1 | IndexHashMismatchError（graph 基於不同版本的 index.scip） |
| 2 | 其他錯誤（檔案讀取失敗等） |

## scip-graph-query

| Exit Code | 意義 |
|-----------|------|
| 0 | 成功 |
| 2 | graph 載入失敗或 node key 無匹配 |
