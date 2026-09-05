// 根级 lint-staged：提交时对暂存文件做格式/静态检查（前端在 engineering/ 有独立工具链，
// 其 eslint/prettier 仅作用于 engineering 内文件，未在此根级挂钩，避免跨包解析依赖）。
module.exports = {
  // Python：ruff（黑盒化/接线后全仓已 ruff 现代化；pyproject.toml 提供 [tool.ruff] 配置）
  // 范围对齐 CI 门禁（pr.yml 仅 `ruff check app/`）：tests/ 等目录存在刻意的
  // sys.path 注入式导入（E402），且不在 CI lint 范围内，不做提交期检查。
  'engineering/python/app/**/*.py': ['ruff check --fix', 'ruff format'],
  // Rust：cargo fmt（不编译，仅格式化）
  '*.rs': ['cargo fmt --']
}
