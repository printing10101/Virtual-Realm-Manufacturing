const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const VERSION_FILE = path.join(ROOT, 'VERSION');

const TARGET_FILES = [
  {
    path: path.join(ROOT, 'package.json'),
    type: 'json',
    field: 'version',
    label: 'package.json'
  },
  {
    path: path.join(ROOT, 'src-tauri', 'Cargo.toml'),
    type: 'toml',
    field: 'version',
    label: 'src-tauri/Cargo.toml'
  },
  {
    path: path.join(ROOT, 'src-tauri', 'tauri.conf.json'),
    type: 'json',
    field: 'version',
    label: 'src-tauri/tauri.conf.json'
  }
];

const SEMVER_RE = /^\d+\.\d+\.\d+$/;

function fail(msg) {
  console.error(`\x1b[31m错误:\x1b[0m ${msg}`);
  process.exit(1);
}

function showHelp() {
  console.log(`
版本同步工具 - 以 VERSION 文件为唯一可信源，同步所有配置文件版本号

用法:
  node version-sync.js [选项]

选项:
  无参数              读取 VERSION 文件版本，同步到所有配置文件
  --version, -v <ver>  指定新版本号（如 2.0.0），同时更新 VERSION 文件和所有配置
  --dry-run           仅模拟执行，显示将要修改的内容，不实际写入文件
  --help, -h          显示此帮助信息

示例:
  node version-sync.js                 # 用 VERSION 文件同步
  node version-sync.js --version 2.0.0 # 设新版本并同步
  node version-sync.js --dry-run       # 模拟运行
`);
  process.exit(0);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { version: null, dryRun: false };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      showHelp();
    } else if (arg === '--dry-run') {
      opts.dryRun = true;
    } else if ((arg === '--version' || arg === '-v') && i + 1 < args.length) {
      opts.version = args[++i];
    } else if (args.length === 1 && i === 0 && !arg.startsWith('-')) {
      opts.version = arg;
    }
  }

  return opts;
}

function validateVersion(version) {
  if (!SEMVER_RE.test(version)) {
    fail(`版本号 "${version}" 不符合 Semantic Versioning 2.0.0 格式（MAJOR.MINOR.PATCH），例如: 1.9.0`);
  }
}

function readVersionFile() {
  if (!fs.existsSync(VERSION_FILE)) {
    fail(`VERSION 文件不存在: ${VERSION_FILE}`);
  }

  const content = fs.readFileSync(VERSION_FILE, 'utf-8').trim();
  if (!content) {
    fail('VERSION 文件为空');
  }

  validateVersion(content);
  return content;
}

function writeVersionFile(version) {
  if (!fs.existsSync(VERSION_FILE)) {
    fail(`VERSION 文件不存在: ${VERSION_FILE}`);
  }
  fs.writeFileSync(VERSION_FILE, version + '\n', 'utf-8');
}

function createBackup(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  const timestamp = Date.now();
  const bakPath = filePath + '.bak.' + timestamp;

  try {
    fs.copyFileSync(filePath, bakPath);
    return bakPath;
  } catch (err) {
    fail(`无法创建备份文件 ${bakPath}: ${err.message}`);
  }
}

function readJson(filePath) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  try {
    return { raw, data: JSON.parse(raw) };
  } catch (err) {
    fail(`JSON 解析失败 ${filePath}: ${err.message}`);
  }
}

function updateJson(filePath, field, newVersion) {
  const { raw, data } = readJson(filePath);

  const oldVersion = data[field];
  if (!oldVersion) {
    fail(`${filePath} 中未找到 "${field}" 字段`);
  }

  if (oldVersion === newVersion) {
    return { changed: false, oldVersion, newVersion };
  }

  data[field] = newVersion;
  const updated = JSON.stringify(data, null, 2) + '\n';
  return { changed: true, oldVersion, newVersion, content: updated };
}

function updateToml(filePath, field, newVersion) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const re = new RegExp(`^(${field}\\s*=\\s*)"[^"]*"`, 'm');
  const match = raw.match(re);

  if (!match) {
    fail(`${filePath} 中未找到 "${field}" 字段`);
  }

  const oldVersion = raw.match(new RegExp(`^${field}\\s*=\\s*"([^"]*)"`, 'm'))[1];

  if (oldVersion === newVersion) {
    return { changed: false, oldVersion, newVersion };
  }

  const updated = raw.replace(re, `$1"${newVersion}"`);
  return { changed: true, oldVersion, newVersion, content: updated };
}

function updateFile(target, newVersion, dryRun) {
  const { path: filePath, type, field, label } = target;

  if (!fs.existsSync(filePath)) {
    fail(`文件不存在: ${filePath}`);
  }

  let result;
  if (type === 'json') {
    result = updateJson(filePath, field, newVersion);
  } else if (type === 'toml') {
    result = updateToml(filePath, field, newVersion);
  }

  if (!result.changed) {
    console.log(`  ${label}: 已为 ${newVersion}，跳过`);
    return false;
  }

  const status = dryRun ? '[模拟]' : '[写入]';
  console.log(`  ${status} ${label}: ${result.oldVersion} → ${newVersion}`);

  if (!dryRun) {
    createBackup(filePath);
    fs.writeFileSync(filePath, result.content, 'utf-8');
  }

  return true;
}

function checkAllConsistent(targetVersion) {
  const issues = [];

  for (const target of TARGET_FILES) {
    if (!fs.existsSync(target.path)) {
      issues.push(`${target.label}: 文件不存在`);
      continue;
    }

    let currentVersion;
    if (target.type === 'json') {
      const { data } = readJson(target.path);
      currentVersion = data[target.field];
    } else if (target.type === 'toml') {
      const raw = fs.readFileSync(target.path, 'utf-8');
      const match = raw.match(new RegExp(`^${target.field}\\s*=\\s*"([^"]*)"`, 'm'));
      currentVersion = match ? match[1] : null;
    }

    if (!currentVersion) {
      issues.push(`${target.label}: 未找到 "${target.field}" 字段`);
    } else if (currentVersion !== targetVersion) {
      issues.push(`${target.label}: ${currentVersion} (期望: ${targetVersion})`);
    }
  }

  return issues;
}

function main() {
  const opts = parseArgs();

  if (opts.version) {
    validateVersion(opts.version);
  }

  const sourceVersion = opts.version || readVersionFile();

  console.log(`\n版本同步工具${opts.dryRun ? ' [模拟模式]' : ''}`);
  console.log(`目标版本: ${sourceVersion}`);
  console.log(`VERSION 源: ${opts.version ? `指定 (${opts.version})` : `文件读取 (${readVersionFile()})`}`);
  console.log('');

  let anyChanged = false;

  for (const target of TARGET_FILES) {
    const changed = updateFile(target, sourceVersion, opts.dryRun);
    if (changed) anyChanged = true;
  }

  if (opts.version && !opts.dryRun) {
    console.log('');
    writeVersionFile(opts.version);
    console.log(`  [写入] VERSION: ${opts.version}`);
  }

  console.log('');
  if (opts.dryRun) {
    console.log('\x1b[33m[模拟完成] 以上变更未实际写入文件。移除 --dry-run 后重新运行以执行实际写入。\x1b[0m');
  } else if (anyChanged) {
    console.log('\x1b[32m同步完成，所有配置文件版本号已统一。\x1b[0m');
  } else {
    console.log('\x1b[32m所有文件版本号已一致，无需更新。\x1b[0m');
  }

  const issues = checkAllConsistent(opts.dryRun ? readVersionFile() : sourceVersion);
  const isDryRunInconsistency = opts.dryRun && opts.version && issues.length > 0;

  if (issues.length > 0 && !isDryRunInconsistency) {
    console.error('\n\x1b[31m版本一致性检查发现以下问题:\x1b[0m');
    issues.forEach(issue => console.error(`  - ${issue}`));
    console.error('');
    process.exit(1);
  }
}

module.exports = { validateVersion, checkAllConsistent, readVersionFile, TARGET_FILES };

if (require.main === module) {
  main();
}