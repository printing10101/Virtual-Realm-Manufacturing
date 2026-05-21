/**
 * 3D 渲染帧率 (FPS) 基准测试
 *
 * 使用 Vitest benchmark 模式测量 Three.js 在不同复杂度场景下的
 * 渲染帧率、帧时间和内存占用。
 *
 * 运行方式: pnpm vitest run --config vitest.bench.config.ts
 */

import { describe, bench, beforeAll, afterAll } from 'vitest'
import * as THREE from 'three'
import { writeFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'

const BENCHMARK_DURATION_MS = 3000
const COMPLEXITY_CONFIGS = {
  low: { geometryCount: 10, geometryType: 'BoxGeometry' as const },
  medium: { geometryCount: 1000, geometryType: 'SphereGeometry' as const },
  high: { geometryCount: 50000, geometryType: 'TorusKnotGeometry' as const },
}

interface BenchmarkResults {
  [key: string]: {
    avg_fps: number
    min_fps: number
    frame_time_ms: number
    memory_usage_mb: number
  }
}

const results: BenchmarkResults = {}

function createScene(complexity: keyof typeof COMPLEXITY_CONFIGS): {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
} {
  const config = COMPLEXITY_CONFIGS[complexity]
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)

  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000)
  camera.position.set(5, 5, 5)
  camera.lookAt(0, 0, 0)

  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(1024, 768)
  renderer.setPixelRatio(1)

  const geometryMap = {
    BoxGeometry: new THREE.BoxGeometry(0.2, 0.2, 0.2),
    SphereGeometry: new THREE.SphereGeometry(0.15, 16, 12),
    TorusKnotGeometry: new THREE.TorusKnotGeometry(0.15, 0.05, 32, 16),
  }
  const geometry = geometryMap[config.geometryType]
  const material = new THREE.MeshStandardMaterial({ color: 0x667eea })

  const gridSize = Math.ceil(Math.pow(config.geometryCount, 1 / 3))
  for (let i = 0; i < config.geometryCount; i++) {
    const mesh = new THREE.Mesh(geometry, material)
    mesh.position.set(
      (i % gridSize - gridSize / 2) * 0.3,
      (Math.floor(i / gridSize) % gridSize - gridSize / 2) * 0.3,
      (Math.floor(i / (gridSize * gridSize)) - gridSize / 2) * 0.3,
    )
    mesh.rotation.set(Math.random(), Math.random(), Math.random())
    scene.add(mesh)
  }

  const ambientLight = new THREE.AmbientLight(0x404060)
  scene.add(ambientLight)
  const dirLight = new THREE.DirectionalLight(0xffffff, 1)
  dirLight.position.set(1, 2, 1)
  scene.add(dirLight)

  return { scene, camera, renderer }
}

function measureFPS(
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  renderer: THREE.WebGLRenderer,
  durationMs: number,
): { avgFps: number; minFps: number; frameTimeMs: number } {
  const frameTimes: number[] = []
  const startTime = performance.now()
  let frameCount = 0
  let lastTime = startTime

  while (performance.now() - startTime < durationMs) {
    const frameStart = performance.now()
    scene.rotation.y = frameCount * 0.01
    renderer.render(scene, camera)
    const frameEnd = performance.now()
    frameTimes.push(frameEnd - frameStart)
    frameCount++
    lastTime = frameEnd
  }

  const elapsed = lastTime - startTime
  const avgFps = (frameCount / elapsed) * 1000
  const minFps = (1 / Math.max(...frameTimes)) * 1000
  const avgFrameTime = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length

  return { avgFps, minFps, frameTimeMs: avgFrameTime }
}

function getMemoryUsage(): number {
  if (typeof process !== 'undefined' && process.memoryUsage) {
    return Math.round(process.memoryUsage().heapUsed / 1024 / 1024 * 100) / 100
  }
  return 0
}

const complexityLevels: Array<keyof typeof COMPLEXITY_CONFIGS> = ['low', 'medium', 'high']

for (const complexity of complexityLevels) {
  describe(`3D 渲染帧率测试 - ${complexity}复杂度`, () => {
    let scene: THREE.Scene
    let camera: THREE.PerspectiveCamera
    let renderer: THREE.WebGLRenderer

    beforeAll(() => {
      const setup = createScene(complexity)
      scene = setup.scene
      camera = setup.camera
      renderer = setup.renderer
    })

    afterAll(() => {
      renderer.dispose()
      scene.clear()
    })

    bench(`FPS - ${complexity}`, () => {
      const memBefore = getMemoryUsage()
      const fps = measureFPS(scene, camera, renderer, BENCHMARK_DURATION_MS)
      const memAfter = getMemoryUsage()

      results[complexity] = {
        avg_fps: Math.round(fps.avgFps * 100) / 100,
        min_fps: Math.round(fps.minFps * 100) / 100,
        frame_time_ms: Math.round(fps.frameTimeMs * 100) / 100,
        memory_usage_mb: Math.round((memAfter - memBefore) * 100) / 100 || memAfter,
      }

      console.log(
        `[${complexity}] FPS: ${results[complexity].avg_fps}, ` +
        `FrameTime: ${results[complexity].frame_time_ms}ms, ` +
        `Memory: ${results[complexity].memory_usage_mb}MB`,
      )
    })
  })
}

afterAll(() => {
  const outputPath = resolve(__dirname, 'reports', 'render_benchmark_results.json')
  const outputDir = dirname(outputPath)
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true })
  }
  writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf-8')
  console.log(`渲染基准测试结果已保存: ${outputPath}`)
})
