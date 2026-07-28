/**
 * 资源卡片 Pinia Store（ADR-012 阶段 6 p6-3）
 *
 * 对接后端 `python/app/api/v1/resource_cards.py` 12 个端点：
 *   - GET    /api/v1/resource-cards/datasets/{dataset_id}                数据集卡片
 *   - PUT    /api/v1/resource-cards/datasets/{dataset_id}/readme         更新数据集 README（upsert）
 *   - GET    /api/v1/resource-cards/datasets/{dataset_id}/lineage        数据集 lineage 摘要
 *   - GET    /api/v1/resource-cards/datasets/{dataset_id}/metrics        数据集指标（版本数/总行数/总大小）
 *   - GET    /api/v1/resource-cards/models                               模型列表（分页+过滤）
 *   - POST   /api/v1/resource-cards/models                               注册新模型产物
 *   - GET    /api/v1/resource-cards/models/{model_id}                    模型卡片详情
 *   - PUT    /api/v1/resource-cards/models/{model_id}                    更新模型卡片
 *   - DELETE /api/v1/resource-cards/models/{model_id}                    删除模型卡片
 *   - GET    /api/v1/resource-cards/models/{model_id}/lineage            模型 lineage 摘要
 *   - GET    /api/v1/resource-cards/models/{model_id}/metrics            模型指标历史
 *   - POST   /api/v1/resource-cards/models/{model_id}/metrics            追加模型指标记录
 *
 * 设计要点：
 *   1. 前端通过此 Store 统一访问资源卡片 API，不直接持有 LineageStore / DatasetStore 状态
 *   2. 卡片聚合（DatasetCard / ModelCard）由后端单次请求拼接，前端不再二次组装
 *   3. README upsert 写操作后自动刷新 currentDatasetCard（保证卡片与 README 一致）
 *   4. 模型 CRUD（register/update/delete）后自动刷新 currentModelCard 与 models 列表
 *   5. 追加指标（appendModelMetrics）后自动刷新 currentModelCard 与模型指标历史
 *   6. 错误统一通过 extractErrorMessage 提取，存入 error state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'
import { extractErrorMessage } from '@/utils/error-handler'
import { API_CONFIG, buildApiPath } from '@/config/api'
import {
  type ModelArtifact,
  type DatasetReadme,
  type LineageSummary,
  type DatasetCard,
  type ModelCard,
  type MetricHistoryEntry,
  type UpsertDatasetReadmeRequest,
  type UpsertDatasetReadmeResponse,
  type RegisterModelRequest,
  type RegisterModelResponse,
  type UpdateModelRequest,
  type UpdateModelResponse,
  type DeleteModelResponse,
  type AppendModelMetricsRequest,
  type AppendModelMetricsResponse,
  type ListModelsParams,
  type ListModelsResponse,
  type GetDatasetCardParams,
  type GetModelCardParams,
} from '@/contracts/resource_card'

// ---------------------------------------------------------------------------
// Store 局部类型（派生 / UI 辅助）
// ---------------------------------------------------------------------------

/** 模型列表分页信息。 */
interface PaginationState {
  total: number
  limit: number
  offset: number
}

/** 数据集指标响应（GET /datasets/{id}/metrics 返回的 payload）。 */
interface DatasetMetricsPayload {
  dataset_id: string
  name: string
  owner_id: string
  status: string
  version_count: number
  total_rows: number
  total_size_bytes: number
  versions: Array<{
    version: string | null
    status: string | null
    row_count: number
    size_bytes: number
    content_hash: string
    created_at: string | null
    created_by: string
  }>
}

/** fetchModels 入参（与后端 Query 参数对齐）。 */
interface FetchModelsParams extends ListModelsParams {}

/** fetchDatasetLineage 入参（与后端 Query 参数对齐）。 */
interface FetchDatasetLineageParams {
  /** 版本号（如 1.0.0），不传则使用最新 published 版本。 */
  version?: string
  /** lineage 深度（1-10，默认 3）。 */
  depth?: number
  /** 每层保留的最大节点数（1-100，默认 10）。 */
  max_nodes_per_layer?: number
}

/** fetchModelLineage 入参（与后端 Query 参数对齐）。 */
interface FetchModelLineageParams {
  /** lineage 深度（1-10，默认 3）。 */
  depth?: number
  /** 每层保留的最大节点数（1-100，默认 10）。 */
  max_nodes_per_layer?: number
}

// ---------------------------------------------------------------------------
// Store 定义
// ---------------------------------------------------------------------------

export const useResourceCardStore = defineStore(
  'resourceCard',
  () => {
    // ===== State：模型列表 =====

    /** 模型列表（list 端点返回的 items）。 */
    const models = ref<ModelArtifact[]>([])
    /** 模型列表分页信息。 */
    const pagination = ref<PaginationState>({
      total: 0,
      limit: 100,
      offset: 0,
    })

    // ===== State：当前数据集卡片 =====

    /** 当前查看的数据集卡片（聚合元数据 + README + lineage 摘要）。 */
    const currentDatasetCard = ref<DatasetCard | null>(null)
    /** 当前数据集 README（最近一次 upsert 响应）。 */
    const currentDatasetReadme = ref<DatasetReadme | null>(null)
    /** 当前数据集 lineage 摘要。 */
    const currentDatasetLineage = ref<LineageSummary | null>(null)
    /** 当前数据集指标（版本数 / 总行数 / 总大小）。 */
    const currentDatasetMetrics = ref<DatasetMetricsPayload | null>(null)

    // ===== State：当前模型卡片 =====

    /** 当前查看的模型卡片（聚合元数据 + snapshot 数 + lineage 摘要）。 */
    const currentModelCard = ref<ModelCard | null>(null)
    /** 当前模型 lineage 摘要。 */
    const currentModelLineage = ref<LineageSummary | null>(null)
    /** 当前模型指标历史（按时间升序）。 */
    const currentModelMetricsHistory = ref<MetricHistoryEntry[]>([])

    // ===== State：最近一次操作响应（用于 UI 提示） =====

    /** 最近一次注册模型响应。 */
    const lastRegisterResult = ref<ModelArtifact | null>(null)
    /** 最近一次更新模型响应。 */
    const lastUpdateResult = ref<ModelArtifact | null>(null)
    /** 最近一次删除模型响应。 */
    const lastDeleteResult = ref<DeleteModelResponse | null>(null)
    /** 最近一次追加指标响应。 */
    const lastAppendMetricsResult = ref<ModelArtifact | null>(null)
    /** 最近一次 upsert README 响应。 */
    const lastUpsertReadmeResult = ref<DatasetReadme | null>(null)

    // ===== Loading 标志 =====

    const loading = ref(false) // 模型列表
    const datasetCardLoading = ref(false)
    const readmeLoading = ref(false)
    const datasetLineageLoading = ref(false)
    const datasetMetricsLoading = ref(false)
    const modelCardLoading = ref(false)
    const modelLineageLoading = ref(false)
    const modelMetricsLoading = ref(false)
    const registering = ref(false)
    const updating = ref(false)
    const deleting = ref(false)
    const appendingMetrics = ref(false)
    const error = ref<string | null>(null)

    // ===== Computed =====

    /** 是否有模型数据。 */
    const hasModels = computed<boolean>(() => models.value.length > 0)

    /** 模型列表当前页码（1-based）。 */
    const currentPage = computed<number>(() =>
      pagination.value.limit > 0
        ? Math.floor(pagination.value.offset / pagination.value.limit) + 1
        : 1,
    )

    /** 模型列表总页数。 */
    const totalPages = computed<number>(() =>
      pagination.value.limit > 0
        ? Math.ceil(pagination.value.total / pagination.value.limit)
        : 1,
    )

    /** 是否有任何加载操作进行中。 */
    const anyLoading = computed<boolean>(
      () =>
        loading.value ||
        datasetCardLoading.value ||
        readmeLoading.value ||
        datasetLineageLoading.value ||
        datasetMetricsLoading.value ||
        modelCardLoading.value ||
        modelLineageLoading.value ||
        modelMetricsLoading.value ||
        registering.value ||
        updating.value ||
        deleting.value ||
        appendingMetrics.value,
    )

    // ===== 内部工具 =====

    /**
     * 解包响应信封：后端统一返回 { code, message, data, request_id }，
     * 此处兼容直接返回 payload 的情况。
     */
    function unwrap<T>(response: unknown): T {
      const r = response as { data?: { data?: T } | T; data?: T }
      if (r && typeof r === 'object' && 'data' in r) {
        const body = r.data as { data?: T } | T
        if (body && typeof body === 'object' && 'data' in body) {
          return (body as { data?: T }).data as T
        }
        return body as T
      }
      return response as T
    }

    /** 从模型列表中按 model_id 移除一条。 */
    function removeFromList(modelId: string): void {
      models.value = models.value.filter((m) => m.model_id !== modelId)
    }

    /** 在模型列表中按 model_id 更新一条。 */
    function updateInList(model: ModelArtifact): void {
      const idx = models.value.findIndex((m) => m.model_id === model.model_id)
      if (idx >= 0) {
        models.value[idx] = model
      }
    }

    // ===== Actions：模型列表 =====

    /**
     * 分页列出模型产物（支持 owner/type/status/tag/name 过滤）.
     * 对应 GET /api/v1/resource-cards/models
     */
    async function fetchModels(
      params: FetchModelsParams = {},
    ): Promise<void> {
      loading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.RESOURCE_CARDS, '/models'),
          {
            params: {
              owner_id: params.owner_id,
              model_type: params.model_type,
              status: params.status,
              tag: params.tag,
              name: params.name,
              limit: params.limit ?? 100,
              offset: params.offset ?? 0,
            },
          },
        )
        const payload = unwrap<ListModelsResponse>(response)
        models.value = payload.items ?? []
        pagination.value = {
          total: payload.total ?? 0,
          limit: payload.limit ?? 100,
          offset: payload.offset ?? 0,
        }
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取模型列表失败')
        models.value = []
      } finally {
        loading.value = false
      }
    }

    // ===== Actions：数据集卡片 =====

    /**
     * 获取数据集卡片（聚合元数据 + 指标 + README + lineage 摘要）.
     * 对应 GET /api/v1/resource-cards/datasets/{dataset_id}
     */
    async function fetchDatasetCard(
      datasetId: string,
      params: GetDatasetCardParams = {},
    ): Promise<void> {
      datasetCardLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/datasets/${datasetId}`,
          ),
          {
            params: {
              include_lineage: params.include_lineage ?? true,
              lineage_depth: params.lineage_depth ?? 3,
            },
          },
        )
        const payload = unwrap<DatasetCard>(response)
        currentDatasetCard.value = payload
        // 卡片自带 readme，同步刷新 currentDatasetReadme
        currentDatasetReadme.value = payload.readme ?? null
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取数据集卡片失败')
        currentDatasetCard.value = null
      } finally {
        datasetCardLoading.value = false
      }
    }

    /**
     * 更新数据集 README（upsert 语义：不存在则创建，存在则覆盖）.
     * 对应 PUT /api/v1/resource-cards/datasets/{dataset_id}/readme
     *
     * 写操作后会刷新 currentDatasetCard，保证卡片与 README 一致。
     */
    async function upsertDatasetReadme(
      datasetId: string,
      request: UpsertDatasetReadmeRequest,
    ): Promise<DatasetReadme | null> {
      readmeLoading.value = true
      error.value = null
      try {
        const response = await http.put(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/datasets/${datasetId}/readme`,
          ),
          request,
        )
        const payload = unwrap<UpsertDatasetReadmeResponse>(response)
        lastUpsertReadmeResult.value = payload
        currentDatasetReadme.value = payload
        // 刷新卡片（readme 字段会同步更新）
        await fetchDatasetCard(datasetId)
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '更新数据集 README 失败')
        return null
      } finally {
        readmeLoading.value = false
      }
    }

    /**
     * 获取数据集 lineage 摘要（按层分组 + 关键路径）.
     * 对应 GET /api/v1/resource-cards/datasets/{dataset_id}/lineage
     */
    async function fetchDatasetLineage(
      datasetId: string,
      params: FetchDatasetLineageParams = {},
    ): Promise<void> {
      datasetLineageLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/datasets/${datasetId}/lineage`,
          ),
          {
            params: {
              version: params.version,
              depth: params.depth ?? 3,
              max_nodes_per_layer: params.max_nodes_per_layer ?? 10,
            },
          },
        )
        const payload = unwrap<LineageSummary>(response)
        currentDatasetLineage.value = payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取数据集 lineage 摘要失败')
        currentDatasetLineage.value = null
      } finally {
        datasetLineageLoading.value = false
      }
    }

    /**
     * 获取数据集指标（版本数 / 总行数 / 总大小 / 各版本明细）.
     * 对应 GET /api/v1/resource-cards/datasets/{dataset_id}/metrics
     */
    async function fetchDatasetMetrics(datasetId: string): Promise<void> {
      datasetMetricsLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/datasets/${datasetId}/metrics`,
          ),
        )
        const payload = unwrap<DatasetMetricsPayload>(response)
        currentDatasetMetrics.value = payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取数据集指标失败')
        currentDatasetMetrics.value = null
      } finally {
        datasetMetricsLoading.value = false
      }
    }

    // ===== Actions：模型卡片 CRUD =====

    /**
     * 注册新模型产物.
     * 对应 POST /api/v1/resource-cards/models
     *
     * 注册成功后会写入本地列表头部，并刷新分页 total。
     */
    async function registerModel(
      request: RegisterModelRequest,
    ): Promise<ModelArtifact | null> {
      registering.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(API_CONFIG.RESOURCE_CARDS, '/models'),
          request,
        )
        const payload = unwrap<RegisterModelResponse>(response)
        lastRegisterResult.value = payload
        // 新模型加入列表头部
        models.value = [payload, ...models.value]
        pagination.value.total += 1
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '注册模型产物失败')
        return null
      } finally {
        registering.value = false
      }
    }

    /**
     * 获取模型卡片详情（聚合元数据 + snapshot 数 + lineage 摘要）.
     * 对应 GET /api/v1/resource-cards/models/{model_id}
     */
    async function fetchModelCard(
      modelId: string,
      params: GetModelCardParams = {},
    ): Promise<void> {
      modelCardLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.RESOURCE_CARDS, `/models/${modelId}`),
          {
            params: {
              include_lineage: params.include_lineage ?? true,
              lineage_depth: params.lineage_depth ?? 3,
            },
          },
        )
        const payload = unwrap<ModelCard>(response)
        currentModelCard.value = payload
        // 卡片自带 metrics_history，同步刷新本地状态
        currentModelMetricsHistory.value = payload.model.metrics_history ?? []
        currentModelLineage.value = payload.lineage_summary ?? null
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取模型卡片失败')
        currentModelCard.value = null
      } finally {
        modelCardLoading.value = false
      }
    }

    /**
     * 更新模型卡片（readme / tags / status / metrics / framework / storage_uri）.
     * 对应 PUT /api/v1/resource-cards/models/{model_id}
     *
     * 更新成功后会刷新 currentModelCard 与 models 列表中的对应条目。
     */
    async function updateModel(
      modelId: string,
      request: UpdateModelRequest,
    ): Promise<ModelArtifact | null> {
      updating.value = true
      error.value = null
      try {
        const response = await http.put(
          buildApiPath(API_CONFIG.RESOURCE_CARDS, `/models/${modelId}`),
          request,
        )
        const payload = unwrap<UpdateModelResponse>(response)
        lastUpdateResult.value = payload
        updateInList(payload)
        // 若当前正在查看该模型卡片，则刷新
        if (currentModelCard.value?.model.model_id === modelId) {
          await fetchModelCard(modelId)
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '更新模型卡片失败')
        return null
      } finally {
        updating.value = false
      }
    }

    /**
     * 删除模型卡片.
     * 对应 DELETE /api/v1/resource-cards/models/{model_id}
     *
     * 删除成功后会从本地列表移除，并清理当前卡片状态（若被删除的正是 currentModelCard）。
     */
    async function deleteModel(
      modelId: string,
    ): Promise<DeleteModelResponse | null> {
      deleting.value = true
      error.value = null
      try {
        const response = await http.delete(
          buildApiPath(API_CONFIG.RESOURCE_CARDS, `/models/${modelId}`),
        )
        const payload = unwrap<DeleteModelResponse>(response)
        lastDeleteResult.value = payload
        removeFromList(modelId)
        if (pagination.value.total > 0) pagination.value.total -= 1
        // 清空当前详情（若被删除的正是 currentModelCard）
        if (currentModelCard.value?.model.model_id === modelId) {
          currentModelCard.value = null
          currentModelLineage.value = null
          currentModelMetricsHistory.value = []
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '删除模型卡片失败')
        return null
      } finally {
        deleting.value = false
      }
    }

    // ===== Actions：模型 lineage 与指标历史 =====

    /**
     * 获取模型 lineage 摘要（按层分组 + 关键路径）.
     * 对应 GET /api/v1/resource-cards/models/{model_id}/lineage
     */
    async function fetchModelLineage(
      modelId: string,
      params: FetchModelLineageParams = {},
    ): Promise<void> {
      modelLineageLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/models/${modelId}/lineage`,
          ),
          {
            params: {
              depth: params.depth ?? 3,
              max_nodes_per_layer: params.max_nodes_per_layer ?? 10,
            },
          },
        )
        const payload = unwrap<LineageSummary>(response)
        currentModelLineage.value = payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取模型 lineage 摘要失败')
        currentModelLineage.value = null
      } finally {
        modelLineageLoading.value = false
      }
    }

    /**
     * 获取模型指标历史（按时间升序的 metrics_history 数组）.
     * 对应 GET /api/v1/resource-cards/models/{model_id}/metrics
     */
    async function fetchModelMetricsHistory(modelId: string): Promise<void> {
      modelMetricsLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/models/${modelId}/metrics`,
          ),
        )
        const payload = unwrap<MetricHistoryEntry[]>(response)
        currentModelMetricsHistory.value = payload ?? []
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取模型指标历史失败')
        currentModelMetricsHistory.value = []
      } finally {
        modelMetricsLoading.value = false
      }
    }

    /**
     * 追加模型指标记录（写入 metrics_history + 更新当前 metrics 快照）.
     * 对应 POST /api/v1/resource-cards/models/{model_id}/metrics
     *
     * 追加成功后会刷新 currentModelCard 与模型指标历史。
     */
    async function appendModelMetrics(
      modelId: string,
      request: AppendModelMetricsRequest,
    ): Promise<ModelArtifact | null> {
      appendingMetrics.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(
            API_CONFIG.RESOURCE_CARDS,
            `/models/${modelId}/metrics`,
          ),
          request,
        )
        const payload = unwrap<AppendModelMetricsResponse>(response)
        lastAppendMetricsResult.value = payload
        updateInList(payload)
        // 同步刷新当前卡片与指标历史
        if (currentModelCard.value?.model.model_id === modelId) {
          await Promise.all([
            fetchModelCard(modelId),
            fetchModelMetricsHistory(modelId),
          ])
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '追加模型指标记录失败')
        return null
      } finally {
        appendingMetrics.value = false
      }
    }

    // ===== 清理 / 重置 =====

    /**
     * 清空当前详情相关的本地状态.
     * 切换数据集/模型或退出详情页时调用，避免旧数据残留。
     */
    function clearCurrent(): void {
      currentDatasetCard.value = null
      currentDatasetReadme.value = null
      currentDatasetLineage.value = null
      currentDatasetMetrics.value = null
      currentModelCard.value = null
      currentModelLineage.value = null
      currentModelMetricsHistory.value = []
    }

    /** 重置整个 Store 到初始状态。 */
    function $reset(): void {
      models.value = []
      pagination.value = { total: 0, limit: 100, offset: 0 }
      currentDatasetCard.value = null
      currentDatasetReadme.value = null
      currentDatasetLineage.value = null
      currentDatasetMetrics.value = null
      currentModelCard.value = null
      currentModelLineage.value = null
      currentModelMetricsHistory.value = []
      lastRegisterResult.value = null
      lastUpdateResult.value = null
      lastDeleteResult.value = null
      lastAppendMetricsResult.value = null
      lastUpsertReadmeResult.value = null
      loading.value = false
      datasetCardLoading.value = false
      readmeLoading.value = false
      datasetLineageLoading.value = false
      datasetMetricsLoading.value = false
      modelCardLoading.value = false
      modelLineageLoading.value = false
      modelMetricsLoading.value = false
      registering.value = false
      updating.value = false
      deleting.value = false
      appendingMetrics.value = false
      error.value = null
    }

    // ===== 导出 =====
    return {
      // State：模型列表
      models,
      pagination,
      // State：当前数据集卡片
      currentDatasetCard,
      currentDatasetReadme,
      currentDatasetLineage,
      currentDatasetMetrics,
      // State：当前模型卡片
      currentModelCard,
      currentModelLineage,
      currentModelMetricsHistory,
      // State：最近一次操作响应
      lastRegisterResult,
      lastUpdateResult,
      lastDeleteResult,
      lastAppendMetricsResult,
      lastUpsertReadmeResult,
      // Loading
      loading,
      datasetCardLoading,
      readmeLoading,
      datasetLineageLoading,
      datasetMetricsLoading,
      modelCardLoading,
      modelLineageLoading,
      modelMetricsLoading,
      registering,
      updating,
      deleting,
      appendingMetrics,
      error,
      // Computed
      hasModels,
      currentPage,
      totalPages,
      anyLoading,
      // Actions：模型列表
      fetchModels,
      // Actions：数据集卡片
      fetchDatasetCard,
      upsertDatasetReadme,
      fetchDatasetLineage,
      fetchDatasetMetrics,
      // Actions：模型卡片 CRUD
      registerModel,
      fetchModelCard,
      updateModel,
      deleteModel,
      // Actions：模型 lineage 与指标历史
      fetchModelLineage,
      fetchModelMetricsHistory,
      appendModelMetrics,
      // 清理 / 重置
      clearCurrent,
      $reset,
    }
  },
)
