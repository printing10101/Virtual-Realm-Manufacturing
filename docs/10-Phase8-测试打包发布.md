# Phase 8: 测试、打包与微软商店发布

> **预计工期**: 4-6 小时 | **前置依赖**: Phase 7 | **下一步**: 附录

## 目标

完成测试、打包配置和微软商店发布准备，包括 Vitest 前端测试、Python 后端测试、Tauri 打包配置、PyInstaller Python 服务打包、MSIX 打包、自动更新配置。

## 验证标准

- [ ] `npm run test` 所有前端测试通过
- [ ] `pytest` 所有后端测试通过
- [ ] `npm run tauri build` 生成可执行安装包
- [ ] PyInstaller 打包生成独立 Python 可执行文件
- [ ] MSIX 打包生成微软商店发布包

---

## 测试配置

### Vitest 前端测试

```typescript
// vitest.config.ts
export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  }
})
```

测试文件：
- `tests/router.test.ts` - 路由测试
- `tests/stores/app.test.ts` - App Store 测试
- `tests/services/tauri.test.ts` - Tauri 服务测试

### Python 后端测试

```python
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
```

测试文件：
- `tests/test_llm_client.py` - LLM 客户端测试
- `tests/test_knowledge.py` - 知识库测试

---

## 打包配置

### Tauri 打包

```json
// src-tauri/tauri.conf.json
{
  "bundle": {
    "active": true,
    "targets": "all",
    "identifier": "com.lingjing.manufacturing",
    "windows": {
      "wix": { "language": "zh-CN" }
    }
  }
}
```

打包命令：`npm run tauri build`

### PyInstaller 打包

```python
# build.spec
a = Analysis(['app/main.py'], ...)
pyz = PYZ(a.pure, ...)
exe = EXE(pyz, ...)
```

打包命令：`python build.py`

### MSIX 打包

```powershell
# scripts/package-msix.ps1
$MSIXConfig = @"
<Identity Name="LingjingManufacturing"
          Publisher="$Publisher"
          Version="$AppVersion.0" />
...
"@
```

---

## 自动更新配置

### Rust 端

```rust
// Cargo.toml
tauri-plugin-updater = "2.0.0"

// lib.rs
use tauri_plugin_updater::UpdaterExt;

#[tauri::command]
async fn check_for_updates(app: tauri::AppHandle) -> Result<Option<String>, String>

#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String>
```

### tauri.conf.json

```json
{
  "plugins": {
    "updater": {
      "active": true,
      "endpoints": ["https://your-update-server.com/api/updater"],
      "pubkey": "your-public-key-here"
    }
  }
}
```

---

## 发布前检查清单

### 功能完整性
- [ ] 所有测试通过
- [ ] 无 TypeScript 类型错误
- [ ] 无 ESLint 警告

### 功能测试
- [ ] 应用正常启动
- [ ] Python 后端连接成功
- [ ] Ollama 服务连接成功
- [ ] 工艺规划工作流正常运行
- [ ] 设置持久化正常

### 打包
- [ ] Tauri 打包成功
- [ ] Python 后端打包成功
- [ ] 安装包可正常运行

---

## 验证清单

1. 前端测试全部通过
2. 后端测试全部通过
3. Tauri 打包成功
4. Python 后端打包成功
5. 发布检查清单完成

---

## 相关文档

- [Phase 7 - 数据持久化](../09-Phase7-数据持久化.md)
- [附录](../11-附录.md)
