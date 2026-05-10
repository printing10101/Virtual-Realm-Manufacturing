import * as THREE from 'three'
import {
  getDefaultConfig,
  createLODForModel,
  countVertices,
  simplifyGeometry,
  calculateDistanceToModel,
  estimateMemoryUsage,
  type LODConfig,
} from '@/utils/lodHelper'

function createTestModel(vertexCount: number): THREE.Object3D {
  const geometry = new THREE.SphereGeometry(10, Math.ceil(Math.sqrt(vertexCount / 2)), Math.ceil(Math.sqrt(vertexCount / 4)))
  const material = new THREE.MeshStandardMaterial({ color: 0x00ff00 })
  return new THREE.Mesh(geometry, material)
}

function testModelSimplification() {
  console.log('Testing model simplification...')

  const vertexCounts = [1000, 10000, 100000]
  const ratios = [0.3, 0.5, 0.8]

  for (const vc of vertexCounts) {
    const model = createTestModel(vc)
    const originalVertices = countVertices(model)
    console.log(`Original model: ${originalVertices} vertices`)

    for (const ratio of ratios) {
      const mesh = model as THREE.Mesh
      const simplified = simplifyGeometry(mesh.geometry, ratio, true)
      const simplifiedVertices = simplified.attributes.position.count
      const reduction = ((1 - simplifiedVertices / originalVertices) * 100).toFixed(1)

      console.log(`  Ratio ${ratio}: ${simplifiedVertices} vertices (${reduction}% reduction)`)
    }
  }
}

function testLODCreation() {
  console.log('\nTesting LOD creation...')

  const model = createTestModel(100000)
  const config = getDefaultConfig()

  const lod = createLODForModel(model, config)
  if (!lod) {
    console.error('LOD creation failed')
    return
  }

  console.log(`LOD levels: ${lod.levels.length}`)

  for (let i = 0; i < lod.levels.length; i++) {
    const level = lod.levels[i]
    const vertices = countVertices(level.object)
    console.log(`  Level ${i} (distance: ${level.distance}): ${vertices} vertices`)
  }

  const originalVertices = countVertices(model)
  const lodVertices = lod.levels[lod.levels.length - 1].object ? countVertices(lod.levels[lod.levels.length - 1].object) : 0
  const reduction = ((1 - lodVertices / originalVertices) * 100).toFixed(1)

  console.log(`Low level reduction: ${reduction}%`)
  console.log(`Meets 80%+ reduction target: ${parseFloat(reduction) >= 80 ? 'YES' : 'NO'}`)
}

function testDistanceCalculation() {
  console.log('\nTesting distance calculation...')

  const model = createTestModel(1000)
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000)

  camera.position.set(0, 0, 100)
  const distance = calculateDistanceToModel(camera, model)
  console.log(`Camera at (0,0,100), Model at origin: distance = ${distance.toFixed(1)}`)

  camera.position.set(50, 50, 50)
  const distance2 = calculateDistanceToModel(camera, model)
  console.log(`Camera at (50,50,50), Model at origin: distance = ${distance2.toFixed(1)}`)
}

function runTests() {
  console.log('=== LOD Helper Tests ===\n')

  testModelSimplification()
  testLODCreation()
  testDistanceCalculation()

  console.log('\n=== Tests Complete ===')
}

runTests()
