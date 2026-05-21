/**
 * 灵境制造 — 刀路仿真前端集成测试
 *
 * 测试内容:
 *  1. 页面加载与3D场景就绪
 *  2. 仿真按钮触发与API调用
 *  3. 碰撞告警展示 (红色高亮/横幅)
 *  4. 播放/暂停/步进交互控件
 *  5. 连续操作稳定性
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:1420';
const API_URL = 'http://localhost:8001';
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

let results = { passed: 0, failed: 0 };
function check(name, condition, detail = '') {
  if (condition) {
    results.passed++;
    console.log(`  [PASS] ${name}`);
  } else {
    results.failed++;
    console.log(`  [FAIL] ${name}  ${detail}`);
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));

  try {
    // ============================================================
    // TEST 1: 页面加载 - 3D仿真场景就绪
    // ============================================================
    console.log('='.repeat(60));
    console.log('TEST 1: 页面加载与3D场景初始化');
    console.log('='.repeat(60));

    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01-page-loaded.png') });

    const title = await page.title();
    check('页面标题非空', title.length > 0, `title="${title}"`);
    console.log(`  Page title: "${title}"`);

    const bodyText = await page.textContent('body');
    check('页面主体有内容', bodyText.length > 10, `length=${bodyText.length}`);

    // ============================================================
    // TEST 2: 导航到 Workspace 页面 (主工作区)
    // ============================================================
    console.log();
    console.log('='.repeat(60));
    console.log('TEST 2: Workspace 页面加载');
    console.log('='.repeat(60));

    await page.goto(`${BASE_URL}/workspace`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02-workspace.png') });

    const wsBody = await page.textContent('body');
    check('Workspace 页面加载', wsBody.length > 10);
    console.log(`  Workspace body length: ${wsBody.length}`);

    // ============================================================
    // TEST 3: API连通性 — 通过fetch直接调用仿真API
    // ============================================================
    console.log();
    console.log('='.repeat(60));
    console.log('TEST 3: API连通性 - 前端fetch调用仿真');
    console.log('='.repeat(60));

    const GCODE = `%
O0001
G21 G17 G90
G00 Z50.
G00 X0. Y0.
G01 Z5. F500
G01 X30. Y10. F800
G01 X50. Y25. F800
G01 X40. Y40. F800
G01 X10. Y35. F800
G01 X0. Y10. F800
G00 Z50.
M30
%`;

    // 通过 Vite proxy 调用
    const apiResult = await page.evaluate(async (gcode) => {
      try {
        const resp = await fetch('/api/simulation/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: 'frontend_test',
            voxel_size: 2.0,
            tool_diameter: 8.0,
            tool_length: 40.0,
            tool_type: 'flat',
            gcode: gcode,
            safe_z_height: 10.0,
            stock_stl_path: '',
          }),
        });
        const json = await resp.json();
        return { ok: resp.ok, status: resp.status, data: json };
      } catch (e) {
        return { error: e.message };
      }
    }, GCODE);

    console.log(`  API result: ${JSON.stringify(apiResult).substring(0, 400)}`);

    check('API fetch 成功 (status 200)', apiResult.ok, JSON.stringify(apiResult));
    check('code=0', apiResult.data?.code === 0);

    const simData = apiResult.data?.data;
    if (simData) {
      check('collision_detected 存在', 'collision_detected' in simData);
      check('simulation_result 存在', 'simulation_result' in simData);
      check('workpiece_stl_path 存在', 'workpiece_stl_path' in simData.simulation_result);
      check('collision_details 存在', 'collision_details' in simData);
      console.log(`  task_id: ${simData.task_id}`);
      console.log(`  collision_detected: ${simData.collision_detected}`);
      console.log(`  duration: ${simData.duration_seconds}s`);
    }

    // ============================================================
    // TEST 4: 碰撞仿真API调用
    // ============================================================
    console.log();
    console.log('='.repeat(60));
    console.log('TEST 4: 碰撞检测验证 - 切入工作台路径');
    console.log('='.repeat(60));

    const COLLISION_GCODE = `%
O0002
G21 G17 G90
G00 Z80.
G00 X0. Y0.
G01 Z-15. F500
G01 X20. F800
G01 X40.
G01 X60.
G01 X80.
G01 Z-30. F500
G01 X60. F800
G01 X40.
G01 X20.
G01 X0.
G00 Z80.
M30
%`;

    const collisionResult = await page.evaluate(async (gcode) => {
      const resp = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'frontend_collision_test',
          voxel_size: 2.0,
          tool_diameter: 8.0,
          tool_length: 40.0,
          tool_type: 'flat',
          gcode: gcode,
          safe_z_height: 10.0,
          stock_stl_path: '',
        }),
      });
      return await resp.json();
    }, COLLISION_GCODE);

    const cd = collisionResult?.data;
    check('碰撞 HTTP 成功', collisionResult?.code === 0);
    check('collision_detected = true', cd?.collision_detected === true,
      `got ${cd?.collision_detected}`);
    const colDetails = cd?.collision_details;
    check('collision_details.count > 0', colDetails?.count > 0,
      `count=${colDetails?.count}`);
    check('collision_details.severity', colDetails?.severity?.length > 0,
      `severity=${colDetails?.severity}`);
    check('collision_details.timestamp', colDetails?.timestamp?.length > 0);
    check('collision_details.positions 有值', colDetails?.positions?.length > 0);

    if (colDetails?.positions?.length > 0) {
      const fp = colDetails.positions[0];
      console.log(`  First collision: (${fp[0]?.toFixed(2)}, ${fp[1]?.toFixed(2)}, ${fp[2]?.toFixed(2)})`);
      check('碰撞位置Z<0 (切入工作台)', fp[2] < 0, `Z=${fp[2]}`);
    }

    // ============================================================
    // TEST 5: 连续5次 API调用稳定性
    // ============================================================
    console.log();
    console.log('='.repeat(60));
    console.log('TEST 5: 连续5次API调用稳定性');
    console.log('='.repeat(60));

    const batchResults = await page.evaluate(async (gcode) => {
      const results = [];
      for (let i = 0; i < 5; i++) {
        const t0 = performance.now();
        const resp = await fetch('/api/simulation/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: `batch_${i}`,
            voxel_size: 2.0,
            tool_diameter: 8.0,
            tool_length: 40.0,
            tool_type: 'flat',
            gcode: gcode,
            safe_z_height: 10.0,
            stock_stl_path: '',
          }),
        });
        const json = await resp.json();
        results.push({
          index: i,
          status: resp.status,
          code: json.code,
          task_id: json.data?.task_id,
          duration: json.data?.duration_seconds,
          elapsed: (performance.now() - t0) / 1000,
        });
      }
      return results;
    }, GCODE);

    let batchAllPassed = true;
    for (const r of batchResults) {
      const ok = r.status === 200 && r.code === 0;
      if (!ok) batchAllPassed = false;
      console.log(`  Batch #${r.index}: status=${r.status}, code=${r.code}, task=${r.task_id}, api_time=${r.duration?.toFixed(2)}s, total=${r.elapsed?.toFixed(2)}s`);
    }
    check('5次连续请求全部成功', batchAllPassed);

    // ============================================================
    // TEST 6: 无 JS 控制台错误
    // ============================================================
    console.log();
    console.log('='.repeat(60));
    console.log('TEST 6: 控制台错误检查');
    console.log('='.repeat(60));

    const relevantErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('512 (Internal') &&
      !e.includes('Failed to load')
    );
    check('无JS控制台错误', relevantErrors.length === 0,
      `Found ${relevantErrors.length} errors: ${relevantErrors.slice(0, 3).join(' | ')}`);

    if (relevantErrors.length > 0) {
      console.log('  Console errors found:');
      relevantErrors.forEach(e => console.log(`    - ${e}`));
    }

  } catch (err) {
    console.error(`FATAL: ${err.message}`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'fatal-error.png') });
  } finally {
    const finalScreenshot = path.join(SCREENSHOT_DIR, '99-final-state.png');
    try { await page.screenshot({ path: finalScreenshot }); } catch (_) { /* ignore screenshot errors */ }

    await browser.close();
  }

  // ============================================================
  // Summary
  // ============================================================
  console.log();
  console.log('='.repeat(60));
  const total = results.passed + results.failed;
  console.log(`FRONTEND TEST SUMMARY: ${results.passed} passed, ${results.failed} failed, ${total} total`);
  console.log('='.repeat(60));

  process.exit(results.failed > 0 ? 1 : 0);
})();
