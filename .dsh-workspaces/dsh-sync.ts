#!/usr/bin/env tsx
/**
 * .dsh-sync 镜像同步工具
 * 用于同步 src-frontend-only/ 与 engineering/src/ 之间的文件
 * 参考 Git LFS 同步策略，仅同步源文件，避免循环依赖
 * 
 * 用法：
 *  - npx tsx dsh-sync.ts           # 预览同步计划
 *  - npx tsx dsh-sync.ts --apply   # 执行同步
 *  - npx tsx dsh-sync.ts --watch   # 实时监听同步
 */

import { readFileSync, writeFileSync, existsSync, statSync, copyFileSync } from 'fs';
import { readdirSync, mkdtempSync } from 'fs';
import { join, relative } from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __dirname = join(fileURLToPath(import.meta.url), '..');
const require = createRequire(import.meta.url);

const ROOT_DIR = join(__dirname, '..');
const MAIN_SRC = 'engineering/src/';
const SOLO_SRC = 'src-frontend-only/';
const SYNC_STATE_FILE = '.dsh-sync-state.json';

// 需要排除的目录（构建产物、依赖、测试文件等）
const EXCLUDE_DIRS = [
  'node_modules',
  '.vite',
  'dist',
  'coverage',
  '__tests__',
  '__snapshots__',
  '*.test.ts',
  '*.test.vue',
  '*.spec.ts',
  '*.spec.vue',
  '.git',
  '.turbo',
  '.dsh-workspaces'
];

interface SyncState {
  lastSyncAt: string;
  fileMap: Record<string, { hash: string; size: number }>;
  totalFiles: number;
}

/**
 * 扫描目录，计算文件 hash（用于增量同步）
 */
async function scanDirectory(dir: string): Promise<Record<string, { hash: string; size: number }>> {
  const fileMap: Record<string, { hash: string; size: number }> = {};
  
  async function walk(currentPath: string) {
    const entries = await readdirSync(currentPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = join(currentPath, entry.name);
      const relativePath = relative(dir, fullPath);
      
      // 跳过排除项
      if (EXCLUDE_DIRS.some(pattern => {
        if (pattern.startsWith('*')) {
          return entry.name.endsWith(pattern.substring(1));
        }
        return entry.name === pattern;
      })) {
        continue;
      }
      
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.isFile()) {
        const content = await readFileSync(fullPath);
        const hash = require('crypto').createHash('md5').update(content).digest('hex');
        fileMap[relativePath] = { hash, size: content.length };
      }
    }
  }
  
  await walk(dir);
  return fileMap;
}

/**
 * 比较两个文件映射，找出差异
 */
function compareMaps(mainMap: Record<string, { hash: string; size: number }>, 
                     soloMap: Record<string, { hash: string; size: number }>): {
  added: string[];
  deleted: string[];
  modified: string[];
  unchanged: number;
} {
  const added: string[] = [];
  const deleted: string[] = [];
  const modified: string[] = [];
  
  for (const file of Object.keys(mainMap)) {
    if (!(file in soloMap)) {
      added.push(file);
    } else if (mainMap[file].hash !== soloMap[file].hash) {
      modified.push(file);
    }
  }
  
  for (const file of Object.keys(soloMap)) {
    if (!(file in mainMap)) {
      deleted.push(file);
    }
  }
  
  return { added, deleted, modified, unchanged: mainMap.length - added.length - modified.length };
}

/**
 * 执行文件同步
 */
async function syncFiles(
  mainPath: string,
  soloPath: string,
  statePath: string,
  dryRun: boolean = true
): Promise<void> {
  console.log('📊 扫描主源码目录...', mainPath);
  const mainMap = await scanDirectory(mainPath);
  
  console.log('📊 扫描镜像源码目录...', soloPath);
  let soloMap: Record<string, { hash: string; size: number }> = {};
  
  if (existsSync(soloPath)) {
    soloMap = await scanDirectory(soloPath);
  }
  
  const differences = compareMaps(mainMap, soloMap);
  
  console.log('\n🔍 同步差异分析:');
  console.log(`   新增文件：${differences.added.length}`);
  console.log(`   删除文件：${differences.deleted.length}`);
  console.log(`   修改文件：${differences.modified.length}`);
  console.log(`   未变文件：${differences.unchanged}`);
  
  if (dryRun) {
    console.log('\n⚠️  预览模式（未执行）');
    if (differences.added.length > 0) {
      console.log('\n📁 将复制到镜像目录:');
      differences.added.slice(0, 10).forEach(f => console.log(`   + ${f}`));
      if (differences.added.length > 10) {
        console.log(`   ... 还有 ${differences.added.length - 10} 个文件`);
      }
    }
    
    if (differences.deleted.length > 0) {
      console.log('\n🗑️  将从镜像目录删除:');
      differences.deleted.slice(0, 5).forEach(f => console.log(`   - ${f}`));
      if (differences.deleted.length > 5) {
        console.log(`   ... 还有 ${differences.deleted.length - 5} 个文件`);
      }
    }
    
    if (differences.modified.length > 0) {
      console.log('\n✏️  将更新镜像目录:');
      differences.modified.slice(0, 5).forEach(f => console.log(`   ~ ${f}`));
      if (differences.modified.length > 5) {
        console.log(`   ... 还有 ${differences.modified.length - 5} 个文件`);
      }
    }
  } else {
    console.log('\n🔄 执行同步...');
    
    // 复制新增/修改的文件
    for (const file of [...differences.added, ...differences.modified]) {
      const srcPath = join(mainPath, file);
      const dstPath = join(soloPath, file);
      const dirPath = join(soloPath, relative(file, ''));
      
      if (!existsSync(dirPath)) {
        await mkdtempSync(join(dirPath, 'sync_' + Date.now()));
      }
      
      copyFileSync(srcPath, dstPath);
      console.log(`   ✓ ${file}`);
    }
    
    // 删除不再存在的文件
    for (const file of differences.deleted) {
      const dstPath = join(soloPath, file);
      if (existsSync(dstPath)) {
        await import('fs').then(m => m.unlinkSync(dstPath));
        console.log(`   ✗ ${file}`);
      }
    }
    
    // 更新状态文件
    const newState: SyncState = {
      lastSyncAt: new Date().toISOString(),
      fileMap: mainMap,
      totalFiles: Object.keys(mainMap).length
    };
    
    writeFileSync(statePath, JSON.stringify(newState, null, 2));
    console.log(`\n✅ 同步完成 (${Object.keys(mainMap).length} 文件)`);
  }
}

/**
 * 主入口
 */
async function main() {
  const args = process.argv.slice(2);
  const dryRun = !args.includes('--apply');
  const watch = args.includes('--watch');
  
  const statePath = join(ROOT_DIR, SYNC_STATE_FILE);
  
  // 加载或初始化状态
  let currentState: SyncState | null = null;
  if (existsSync(statePath)) {
    currentState = JSON.parse(readFileSync(statePath, 'utf-8'));
    console.log('💾 加载同步状态...');
    console.log(`   上次同步：${currentState.lastSyncAt}`);
    console.log(`   文件数量：${currentState.totalFiles}`);
  }
  
  await syncFiles(
    join(ROOT_DIR, MAIN_SRC),
    join(ROOT_DIR, SOLO_SRC),
    statePath,
    dryRun
  );
  
  if (watch && dryRun) {
    console.log('\n📡 实时监控模式...');
    // TODO: 实现 fs.watch 监听
    console.log('（实时监听功能待实现）');
  }
}

main().catch(console.error);
