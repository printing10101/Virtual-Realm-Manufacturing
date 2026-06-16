/**
 * 仿真结果API客户端
 * 负责获取仿真数据、缓存管理和错误处理
 */

import http from '@/utils/http'
import type { SimulationResult, SimulationStatus } from '@/types'

/** 仿真结果数据（扩展用于可视化） */
export interface SimulationVisualizationData {
  task_id: string
  force_data?: ForceData[]
  temperature_data?: TemperatureData[]
  vibration_data?: VibrationData[]
  timestamp: number
}

/** 力数据点 */
export interface ForceData {
  position: [number, number, number]
  direction: [number, number, number]
  magnitude: number
  timestamp: number
}

/** 温度数据点 */
export interface TemperatureData {
  position: [number, number, number]
  temperature: number
  timestamp: number
}

/** 振动数据点 */
export interface VibrationData {
  position: [number, number, number]
  amplitude: number
  frequency: number
  timestamp: number
}

/** API响应包装 */
interface ApiResponse<T> {
  data: T
  message?: string
  status?: number
}

/** 缓存配置 */
const CACHE_CONFIG = {
  maxAge: 5 * 60 * 1000, // 5分钟缓存
  maxSize: 50, // 最多缓存50个结果
}

/** 缓存存储 */
const cache = new Map<string, { data: SimulationVisualizationData; timestamp: number }>()

/**
 * 清理过期缓存
 */
function cleanupCache(): void {
  const now = Date.now()
  const expiredKeys: string[] = []

  cache.forEach((value, key) => {
    if (now - value.timestamp > CACHE_CONFIG.maxAge) {
      expiredKeys.push(key)
    }
  })

  expiredKeys.forEach((key) => cache.delete(key))

  // 如果缓存仍然过大，删除最旧的条目
  while (cache.size > CACHE_CONFIG.maxSize) {
    const oldestKey = cache.keys().next().value
    if (oldestKey) {
      cache.delete(oldestKey)
    }
  }
}

/**
 * 获取仿真结果
 * @param taskId 任务ID
 * @param forceRefresh 是否强制刷新（忽略缓存）
 */
export async function getSimulationResult(
  taskId: string,
  forceRefresh = false
): Promise<SimulationVisualizationData> {
  // 检查缓存
  if (!forceRefresh) {
    const cached = cache.get(taskId)
    if (cached && Date.now() - cached.timestamp < CACHE_CONFIG.maxAge) {
      return cached.data
    }
  }

  try {
    // 获取仿真状态和结果
    const statusResponse = await http.get<ApiResponse<SimulationStatus>>(
      `/simulation/status/${taskId}`
    )

    const status = statusResponse.data.data

    if (status.status !== 'completed' || !status.result) {
      throw new Error(`仿真任务未完成或失败: ${status.status}`)
    }

    // 获取仿真结果详情
    const resultResponse = await http.get<ApiResponse<SimulationResult>>(
      `/simulation/result/${taskId}`
    )

    const result = resultResponse.data.data

    // 转换为可视化数据格式
    const visualizationData = convertToVisualizationData(result)

    // 更新缓存
    cleanupCache()
    cache.set(taskId, {
      data: visualizationData,
      timestamp: Date.now(),
    })

    return visualizationData
  } catch (error) {
    console.error('获取仿真结果失败:', error)
    throw error
  }
}

/**
 * 将仿真结果转换为可视化数据
 */
function convertToVisualizationData(result: SimulationResult): SimulationVisualizationData {
  const visualizationData: SimulationVisualizationData = {
    task_id: result.task_id,
    timestamp: Date.now(),
    force_data: [],
    temperature_data: [],
    vibration_data: [],
  }

  // 如果有碰撞位置数据，生成力矢量
  if (result.collision_details && result.collision_details.positions.length > 0) {
    visualizationData.force_data = result.collision_details.positions.map((pos, index) => ({
      position: pos,
      direction: [0, 0, -1], // 默认方向，实际应该从仿真数据计算
      magnitude: result.collision_details.severity === 'critical' ? 1000 : 500,
      timestamp: Date.now(),
    }))
  }

  // 生成温度数据（基于体素网格）
  if (result.simulation_result && result.simulation_result.voxel_count > 0) {
    // 这里应该从后端获取实际的温度场数据
    // 暂时生成示例数据
    const bbox = result.simulation_result.original_bbox
    if (bbox) {
      const minX = bbox.min_x || 0
      const maxX = bbox.max_x || 100
      const minY = bbox.min_y || 0
      const maxY = bbox.max_y || 100
      const minZ = bbox.min_z || 0
      const maxZ = bbox.max_z || 50

      // 生成网格点温度数据
      const gridSize = 10
      for (let x = minX; x <= maxX; x += (maxX - minX) / gridSize) {
        for (let y = minY; y <= maxY; y += (maxY - minY) / gridSize) {
          for (let z = minZ; z <= maxZ; z += (maxZ - minZ) / gridSize) {
            // 模拟温度分布（中心温度高，边缘温度低）
            const centerX = (minX + maxX) / 2
            const centerY = (minY + maxY) / 2
            const centerZ = (minZ + maxZ) / 2
            const distance = Math.sqrt(
              Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2) + Math.pow(z - centerZ, 2)
            )
            const maxDistance = Math.sqrt(
              Math.pow(maxX - minX, 2) + Math.pow(maxY - minY, 2) + Math.pow(maxZ - minZ, 2)
            )
            const temperature = 20 + 80 * (1 - distance / maxDistance)

            visualizationData.temperature_data!.push({
              position: [x, y, z],
              temperature,
              timestamp: Date.now(),
            })
          }
        }
      }
    }
  }

  // 生成振动数据（基于刀具路径）
  if (result.toolpath_segment_count > 0) {
    // 这里应该从后端获取实际的振动数据
    // 暂时生成示例数据
    for (let i = 0; i < result.toolpath_segment_count; i++) {
      visualizationData.vibration_data!.push({
        position: [i * 10, 0, 0], // 简化的位置
        amplitude: Math.random() * 0.1, // 随机振幅
        frequency: 50 + Math.random() * 50, // 50-100Hz
        timestamp: Date.now(),
      })
    }
  }

  return visualizationData
}

/**
 * 清除指定任务的缓存
 */
export function clearSimulationCache(taskId?: string): void {
  if (taskId) {
    cache.delete(taskId)
  } else {
    cache.clear()
  }
}

/**
 * 获取缓存统计信息
 */
export function getCacheStats(): { size: number; maxAge: number; maxSize: number } {
  return {
    size: cache.size,
    maxAge: CACHE_CONFIG.maxAge,
    maxSize: CACHE_CONFIG.maxSize,
  }
}
