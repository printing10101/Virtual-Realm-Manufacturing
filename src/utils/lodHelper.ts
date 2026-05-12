import * as THREE from 'three'

export interface LODLevel {
  distance: number
  model: THREE.Object3D
  simplificationRatio: number
  vertexCount: number
}

export interface LODConfig {
  enabled: boolean
  levels: Array<{
    distance: number
    simplificationRatio: number
  }>
  useEdgeCollapse: boolean
  preserveMaterials: boolean
  onLevelChange?: (level: number) => void
}

export interface LODPerformanceMetrics {
  originalVertexCount: number
  lodVertexCounts: number[]
  memoryBeforeKB: number
  memoryAfterKB: number
  fpsWithLOD: number
  fpsWithoutLOD: number
}

export function getDefaultConfig(): LODConfig {
  return {
    enabled: true,
    levels: [
      { distance: 50, simplificationRatio: 0 },
      { distance: 150, simplificationRatio: 0.5 },
      { distance: 300, simplificationRatio: 0.8 },
    ],
    useEdgeCollapse: true,
    preserveMaterials: true,
  }
}

export function countVertices(object: THREE.Object3D): number {
  let count = 0
  object.traverse((child) => {
    if (child instanceof THREE.Mesh && child.geometry) {
      const geometry = child.geometry
      if (geometry.attributes.position) {
        count += geometry.attributes.position.count
      }
    }
  })
  return count
}

function _estimateMeshSize(object: THREE.Object3D): number {
  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())
  return Math.max(size.x, size.y, size.z)
}

function cloneGeometry(geometry: THREE.BufferGeometry): THREE.BufferGeometry {
  const cloned = new THREE.BufferGeometry()

  for (const [name, attribute] of Object.entries(geometry.attributes)) {
    if (attribute instanceof THREE.BufferAttribute) {
      cloned.setAttribute(name, attribute.clone())
    }
  }

  if (geometry.index) {
    cloned.setIndex(geometry.index.clone())
  }

  return cloned
}

function simplifyGeometryEdgeCollapse(
  geometry: THREE.BufferGeometry,
  ratio: number
): THREE.BufferGeometry {
  if (ratio <= 0) {
    return cloneGeometry(geometry)
  }

  const simplified = geometry.clone()

  if (!simplified.index) {
    const indices: number[] = []
    const vertexCount = simplified.attributes.position.count
    for (let i = 0; i < vertexCount; i += 3) {
      indices.push(i, i + 1, i + 2)
    }
    simplified.setIndex(indices)
  }

  const positionAttr = simplified.attributes.position
  const vertexCount = positionAttr.count
  const targetCount = Math.max(Math.floor(vertexCount * (1 - ratio)), 4)

  if (targetCount >= vertexCount) {
    return simplified
  }

  const oldPosition = new Float32Array(positionAttr.array)
  if (!simplified.index) {
    throw new Error('Geometry must have index for edge collapse simplification')
  }
  const oldIndex = simplified.index.array

  const vertexUsed = new Uint8Array(vertexCount)
  const vertexRemap = new Int32Array(vertexCount).fill(-1)

  const keepCount = targetCount
  const indicesToKeep: number[] = []

  const tempV1 = new THREE.Vector3()
  const tempV2 = new THREE.Vector3()

  for (let i = 0; i < oldIndex.length; i++) {
    const idx = oldIndex[i]
    if (!vertexUsed[idx] && indicesToKeep.length < keepCount) {
      vertexUsed[idx] = 1
      indicesToKeep.push(idx)
    }
  }

  while (indicesToKeep.length < keepCount) {
    for (let i = 0; i < vertexCount && indicesToKeep.length < keepCount; i++) {
      if (!vertexUsed[i]) {
        vertexUsed[i] = 1
        indicesToKeep.push(i)
      }
    }
    break
  }

  for (let i = 0; i < indicesToKeep.length; i++) {
    vertexRemap[indicesToKeep[i]] = i
  }

  const maxDist = 20
  for (let i = 0; i < vertexCount; i++) {
    if (vertexRemap[i] === -1) {
      tempV1.set(oldPosition[i * 3], oldPosition[i * 3 + 1], oldPosition[i * 3 + 2])
      let minDist = Infinity
      let nearestIdx = 0
      for (const keepIdx of indicesToKeep) {
        tempV2.set(
          oldPosition[keepIdx * 3],
          oldPosition[keepIdx * 3 + 1],
          oldPosition[keepIdx * 3 + 2]
        )
        const d = tempV1.distanceTo(tempV2)
        if (d < minDist) {
          minDist = d
          nearestIdx = keepIdx
        }
      }
      if (minDist < maxDist) {
        vertexRemap[i] = vertexRemap[nearestIdx]
      } else {
        const fallback = indicesToKeep[Math.floor(Math.random() * indicesToKeep.length)]
        vertexRemap[i] = vertexRemap[fallback]
      }
    }
  }

  const newPosition = new Float32Array(keepCount * 3)
  for (let i = 0; i < indicesToKeep.length; i++) {
    const srcIdx = indicesToKeep[i]
    newPosition[i * 3] = oldPosition[srcIdx * 3]
    newPosition[i * 3 + 1] = oldPosition[srcIdx * 3 + 1]
    newPosition[i * 3 + 2] = oldPosition[srcIdx * 3 + 2]
  }

  simplified.setAttribute(
    'position',
    new THREE.BufferAttribute(newPosition, 3)
  )

  const newIndex: number[] = []
  for (let i = 0; i < oldIndex.length; i += 3) {
    const a = vertexRemap[oldIndex[i]]
    const b = vertexRemap[oldIndex[i + 1]]
    const c = vertexRemap[oldIndex[i + 2]]

    if (a !== b && b !== c && a !== c) {
      newIndex.push(a, b, c)
    }
  }

  if (newIndex.length > 0) {
    simplified.setIndex(newIndex)
  }

  simplified.computeVertexNormals()

  return simplified
}

function simplifyGeometryVertexRemoval(
  geometry: THREE.BufferGeometry,
  ratio: number
): THREE.BufferGeometry {
  if (ratio <= 0) {
    return cloneGeometry(geometry)
  }

  const simplified = geometry.clone()

  const positionAttr = simplified.attributes.position
  const totalVertices = positionAttr.count
  const keepCount = Math.max(Math.floor(totalVertices * (1 - ratio)), 4)
  const step = Math.max(1, Math.floor(totalVertices / keepCount))

  const keepIndices = new Set<number>()
  for (let i = 0; i < totalVertices; i += step) {
    keepIndices.add(i)
  }
  while (keepIndices.size < keepCount && keepIndices.size < totalVertices) {
    keepIndices.add(Math.floor(Math.random() * totalVertices))
  }

  const sortedIndices = Array.from(keepIndices).sort((a, b) => a - b)

  const remap = new Map<number, number>()
  sortedIndices.forEach((oldIdx, newIdx) => {
    remap.set(oldIdx, newIdx)
  })

  const newPositions = new Float32Array(sortedIndices.length * 3)
  for (let i = 0; i < sortedIndices.length; i++) {
    const oldIdx = sortedIndices[i]
    newPositions[i * 3] = positionAttr.getX(oldIdx)
    newPositions[i * 3 + 1] = positionAttr.getY(oldIdx)
    newPositions[i * 3 + 2] = positionAttr.getZ(oldIdx)
  }

  simplified.setAttribute(
    'position',
    new THREE.BufferAttribute(newPositions, 3)
  )

  if (simplified.index) {
    const oldIndex = simplified.index.array
    const newIndex: number[] = []
    for (let i = 0; i < oldIndex.length; i += 3) {
      const a = remap.get(oldIndex[i])
      const b = remap.get(oldIndex[i + 1])
      const c = remap.get(oldIndex[i + 2])

      if (a !== undefined && b !== undefined && c !== undefined) {
        if (a !== b && b !== c && a !== c) {
          newIndex.push(a, b, c)
        }
      }
    }

    if (newIndex.length > 0) {
      simplified.setIndex(newIndex)
    } else {
      simplified.index = null
    }
  }

  simplified.computeVertexNormals()

  return simplified
}

export function simplifyGeometry(
  geometry: THREE.BufferGeometry,
  ratio: number,
  useEdgeCollapse: boolean = true
): THREE.BufferGeometry {
  if (useEdgeCollapse) {
    return simplifyGeometryEdgeCollapse(geometry, ratio)
  }
  return simplifyGeometryVertexRemoval(geometry, ratio)
}

function cloneObjectWithMaterials(
  object: THREE.Object3D,
  simplifyGeometryFn?: (geometry: THREE.BufferGeometry) => THREE.BufferGeometry
): THREE.Object3D {
  const clone = object.clone()

  if (simplifyGeometryFn) {
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh && child.geometry) {
        child.geometry = simplifyGeometryFn(child.geometry)
      }
    })
  }

  return clone
}

export function createLODObject(
  originalModel: THREE.Object3D,
  config: LODConfig
): { lod: THREE.LOD; metrics: LODPerformanceMetrics } {
  const lod = new THREE.LOD()

  const originalVertexCount = countVertices(originalModel)
  const lodVertexCounts: number[] = []

  const levels = config.levels.length > 0 ? config.levels : getDefaultConfig().levels

  const memoryBeforeKB = 0
  const memoryAfterKB = 0

  for (let i = 0; i < levels.length; i++) {
    const level = levels[i]
    const isHighestLevel = i === 0

    let modelForLevel: THREE.Object3D

    if (isHighestLevel || level.simplificationRatio <= 0) {
      modelForLevel = originalModel.clone()
    } else {
      const simplifyFn = (geometry: THREE.BufferGeometry) =>
        simplifyGeometry(geometry, level.simplificationRatio, config.useEdgeCollapse)

      modelForLevel = cloneObjectWithMaterials(originalModel, simplifyFn)
    }

    const vertexCount = countVertices(modelForLevel)
    lodVertexCounts.push(vertexCount)

    lod.addLevel(modelForLevel, level.distance)
  }

  if (levels.length === 1) {
    const highLevel = originalModel.clone()
    lod.addLevel(highLevel, 0)
    lodVertexCounts.push(originalVertexCount)
  }

  const tempScene = new THREE.Scene()
  tempScene.add(originalModel)

  lod.updateMatrixWorld()

  return {
    lod,
    metrics: {
      originalVertexCount,
      lodVertexCounts,
      memoryBeforeKB: memoryBeforeKB || originalVertexCount * 0.1,
      memoryAfterKB: memoryAfterKB || lodVertexCounts.reduce((a, b) => a + b, 0) * 0.1,
      fpsWithLOD: 0,
      fpsWithoutLOD: 0,
    },
  }
}

export function createLODForModel(
  model: THREE.Object3D,
  config: LODConfig
): THREE.LOD | null {
  if (!config.enabled) {
    return null
  }

  if (model instanceof THREE.LOD) {
    return model
  }

  const { lod } = createLODObject(model, config)

  return lod
}

export function updateLOD(
  lod: THREE.LOD,
  camera: THREE.Camera
): void {
  if (!lod || !camera) return

  lod.update(camera)
}

export function setLODLevelVisibility(
  lod: THREE.LOD,
  targetLevel: number
): void {
  const levels = lod.levels

  for (let i = 0; i < levels.length; i++) {
    levels[i].object.visible = i === targetLevel
  }
}

export function getLODCurrentLevel(lod: THREE.LOD): number {
  return lod.getCurrentLevel()
}

export function calculateDistanceToModel(
  camera: THREE.Camera,
  model: THREE.Object3D
): number {
  const cameraPos = camera.position.clone()
  const modelBox = new THREE.Box3().setFromObject(model)
  const modelCenter = modelBox.getCenter(new THREE.Vector3())

  return cameraPos.distanceTo(modelCenter)
}

export function measurePerformance(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera,
  durationMs: number = 2000
): Promise<number> {
  return new Promise((resolve) => {
    let frames = 0
    const startTime = performance.now()

    function countFrame() {
      frames++
      renderer.render(scene, camera)

      const elapsed = performance.now() - startTime
      if (elapsed < durationMs) {
        requestAnimationFrame(countFrame)
      } else {
        const fps = (frames / elapsed) * 1000
        resolve(Math.round(fps))
      }
    }

    countFrame()
  })
}

export function estimateMemoryUsage(object: THREE.Object3D): number {
  let memoryKB = 0

  object.traverse((child) => {
    if (child instanceof THREE.Mesh && child.geometry) {
      const geometry = child.geometry

      for (const attr of Object.values(geometry.attributes)) {
        if (attr instanceof THREE.BufferAttribute) {
          memoryKB += attr.array.byteLength / 1024
        }
      }

      if (geometry.index) {
        memoryKB += geometry.index.array.byteLength / 1024
      }
    }

    if (child instanceof THREE.Mesh && child.material) {
      const materials = Array.isArray(child.material) ? child.material : [child.material]
      for (const _mat of materials) {
        memoryKB += 50
      }
    }
  })

  return Math.round(memoryKB)
}

export function updateLODConfig(
  config: LODConfig,
  updates: Partial<LODConfig>
): LODConfig {
  return {
    ...config,
    ...updates,
    levels: updates.levels || config.levels,
  }
}

export function getLODStats(lod: THREE.LOD): string {
  const stats: string[] = []
  const levels = lod.levels

  for (let i = 0; i < levels.length; i++) {
    const level = levels[i]
    const vertexCount = countVertices(level.object)
    const label = i === 0 ? 'High' : i === 1 ? 'Medium' : 'Low'
    stats.push(`${label} (distance: ${level.distance}): ${vertexCount} vertices`)
  }

  return stats.join('\n')
}
