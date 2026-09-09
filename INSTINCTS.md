# INSTINCTS

## 公开仓本机路径（2026-09-09）

- **触发**：CI 基线报告、研究脚本日志、软著收集脚本会写绝对路径。
- **正确做法**：生成报告时剥离 `C:\Users\<用户名>\...`；提交前扫描 `Users\\Lenovo`。
- **证据**：`.ci_baseline_response_model.json` 等 27 文件已替换为 `C:\Users\<user>`。

## 文档中的 PEM

- **触发**：TLS/证书说明文档贴示例。
- **正确做法**：用 `<PEM 示例>` 占位，不要贴 `BEGIN PRIVATE KEY` 字样，避免密钥扫描误报。
- **证据**：`deploy/nginx/README_TLS.md` 已改为占位文本。

## 论文/专利草稿

- **触发**：`output/paper-writer/`、`outputs/patent-mining/`。
- **正确做法**：不进公开仓；需要时另建私有仓或本地归档。
- **证据**：2026-09-09 推送时显式排除。
