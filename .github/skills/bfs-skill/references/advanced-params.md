# 進階參數參考

## scip-extract

| 參數 | 說明 |
|------|------|
| `--output-modules` | 僅輸出指定 SCIP package 的 Markdown（逗號分隔，BFS 仍完整展開）。模組名稱為 SCIP package name（如 `scip_deep_context`），非 Python import path。⚠️ 對單一 SCIP package 專案無法做子模組過濾，改用 `--output-symbol-prefix` |
| `--output-symbol-prefix` | 僅輸出 descriptor 以指定前綴開頭的節點 Markdown（逗號分隔，BFS 仍完整展開）。前綴為 SCIP descriptor 的 module path（以 `/` 分隔），case-sensitive。適用於單一 SCIP package 專案的子模組過濾。可用 `--raw-symbols` 查看完整 descriptor 確認前綴格式 |
| `--include-fields` | BFS 包含 field/property symbols |
| `--no-default-excludes` | 停用預設排除（含 local variable） |
| `--exclude-patterns` | 自訂排除 pattern（逗號分隔） |
| `--project-modules` | 限制 BFS 只追蹤指定模組（影響 BFS 邊界，與 `--output-modules` 不同） |
| `--no-dedup` | 停用 containment dedup |
| `--raw-symbols` | 顯示完整 SCIP symbol |
| `--test-file-pattern` | 批次提取：匹配測試檔名（與 `--entry-file` 互斥） |
| `--test-method-pattern` | 批次提取：匹配測試方法名 |

> **`--project-modules` vs `--output-modules` vs `--output-symbol-prefix`**：`--project-modules` 控制 BFS 展開邊界（不追蹤模組外的呼叫）；`--output-modules` 控制 Markdown 輸出的 SCIP package 過濾（BFS 完整展開但只渲染指定 package）；`--output-symbol-prefix` 控制 Markdown 輸出的 descriptor prefix 過濾（適用於單 SCIP package 專案的子模組過濾）。三者可獨立或組合使用，`--output-modules` 和 `--output-symbol-prefix` 同時啟用時為 AND 關係。

## scip-graph-query

| 參數 | 說明 |
|------|------|
| `--with-source` | 輸出從 JSON 切換為 Markdown，附帶各節點源碼（與 `--list-nodes` 互斥） |
| `--project-root` | 專案根目錄，`--with-source` 時必須提供，用於定位源碼檔案 |
