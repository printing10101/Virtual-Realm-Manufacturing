/**
 * 项目级 Git 同步 Pinia Store（ADR-011 阶段 6 p6-2）
 *
 * 对接后端 `python/app/api/v1/project_sync.py` 13 个端点：
 *   - POST   /api/v1/project-sync/projects                          创建项目（含 git init）
 *   - GET    /api/v1/project-sync/projects                          项目列表（分页/过滤）
 *   - GET    /api/v1/project-sync/projects/{project_id}             项目详情
 *   - DELETE /api/v1/project-sync/projects/{project_id}             删除项目（可选 purge_repo）
 *   - GET    /api/v1/project-sync/projects/{project_id}/status      查询 Git 状态
 *   - POST   /api/v1/project-sync/projects/{project_id}/commit      提交变更
 *   - POST   /api/v1/project-sync/projects/{project_id}/push        推送远端
 *   - POST   /api/v1/project-sync/projects/{project_id}/pull        拉取远端
 *   - POST   /api/v1/project-sync/projects/{project_id}/resources   添加资源引用
 *   - GET    /api/v1/project-sync/projects/{project_id}/resources   列出资源引用
 *   - DELETE /api/v1/project-sync/projects/{project_id}/resources   删除资源引用
 *   - GET    /api/v1/project-sync/projects/{project_id}/records     查询同步记录
 *   - POST   /api/v1/project-sync/clone                             克隆远端项目
 *
 * 设计要点：
 *   1. 前端通过此 Store 统一访问项目同步 API，不直接持有 Git 仓库状态
 *   2. 资源引用（ResourceRef）通过 URI + content_hash 实现内容寻址同步
 *   3. 同步状态机（clean/dirty/ahead/behind/conflict/error）由后端推导
 *   4. commit/push/pull/push 等写操作后自动刷新 currentProject 与 projectStatus
 *   5. 错误统一通过 extractErrorMessage 提取，存入 error state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'
import { extractErrorMessage } from '@/utils/error-handler'
import { API_CONFIG, buildApiPath } from '@/config/api'
import {
  type ProjectSyncManifest,
  type GetProjectResponse,
  type ProjectStatusResponse,
  type ResourceRefRecord,
  type SyncRecord,
  type ListProjectsResponse,
  type CreateProjectRequest,
  type CloneProjectRequest,
  type CommitProjectResponse,
  type SyncOperationResponse,
  type DeleteProjectResponse,
  type AddResourceRefRequest,
  type AddResourceRefResponse,
  type ListResourceRefsParams,
  type ListResourceRefsResponse,
  type RemoveResourceRefResponse,
  type ListSyncRecordsResponse,
  type SyncStatus,
  type SyncDirection,
} from '@/contracts/project_sync'

// ---------------------------------------------------------------------------
// Store 局部类型（派生 / UI 辅助）
// ---------------------------------------------------------------------------

/** 项目列表分页信息（从 list 响应派生）。 */
interface PaginationState {
  total: number
  limit: number
  offset: number
}

/** 同步记录分页信息（独立维护，避免与项目列表分页冲突）。 */
interface RecordsPaginationState {
  total: number
  limit: number
  offset: number
}

/** fetchProjects 入参（与后端 Query 参数对齐）。 */
interface FetchProjectsParams {
  status?: SyncStatus
  author?: string
  limit?: number
  offset?: number
}

/** fetchProject 入参。 */
interface FetchProjectParams {
  /** 是否包含资源引用列表（默认 true）。 */
  includeRefs?: boolean
  /** 是否包含同步记录列表（默认 false，避免大查询）。 */
  includeRecords?: boolean
}

/** fetchSyncRecords 入参（与后端 Query 参数对齐）。 */
interface FetchSyncRecordsParams {
  direction?: SyncDirection
  limit?: number
  offset?: number
}

// ---------------------------------------------------------------------------
// Store 定义
// ---------------------------------------------------------------------------

export const useProjectSyncStore = defineStore(
  'projectSync',
  () => {
    // ===== State =====

    /** 项目列表（list 端点返回的 items）。 */
    const projects = ref<ProjectSyncManifest[]>([])
    /** 当前查看的项目详情（含主表 + 可选资源引用 / 同步记录）。 */
    const currentProject = ref<GetProjectResponse | null>(null)
    /** 当前项目的 Git 状态（含 ahead/behind 计数与变更文件列表）。 */
    const projectStatus = ref<ProjectStatusResponse | null>(null)
    /** 当前项目的资源引用列表（独立维护，便于资源管理页直接消费）。 */
    const resourceRefs = ref<ResourceRefRecord[]>([])
    /** 当前项目的同步记录列表（按时间倒序）。 */
    const syncRecords = ref<SyncRecord[]>([])
    /** 项目列表分页信息。 */
    const pagination = ref<PaginationState>({
      total: 0,
      limit: 50,
      offset: 0,
    })
    /** 同步记录分页信息。 */
    const recordsPagination = ref<RecordsPaginationState>({
      total: 0,
      limit: 50,
      offset: 0,
    })

    /** 最近一次创建项目响应（用于 UI 提示）。 */
    const lastCreateResult = ref<ProjectSyncManifest | null>(null)
    /** 最近一次克隆项目响应。 */
    const lastCloneResult = ref<ProjectSyncManifest | null>(null)
    /** 最近一次提交响应。 */
    const lastCommitResult = ref<CommitProjectResponse | null>(null)
    /** 最近一次 push/pull 响应。 */
    const lastSyncResult = ref<SyncOperationResponse | null>(null)
    /** 最近一次删除项目响应。 */
    const lastDeleteResult = ref<DeleteProjectResponse | null>(null)
    /** 最近一次添加资源引用响应。 */
    const lastAddRefResult = ref<AddResourceRefResponse | null>(null)
    /** 最近一次删除资源引用响应。 */
    const lastRemoveRefResult = ref<RemoveResourceRefResponse | null>(null)

    // ===== Loading 标志 =====
    const loading = ref(false)
    const detailLoading = ref(false)
    const statusLoading = ref(false)
    const creating = ref(false)
    const cloning = ref(false)
    const deleting = ref(false)
    const committing = ref(false)
    const pushing = ref(false)
    const pulling = ref(false)
    const refsLoading = ref(false)
    const addingRef = ref(false)
    const removingRef = ref(false)
    const recordsLoading = ref(false)
    const error = ref<string | null>(null)

    // ===== Computed =====

    /** 是否有项目数据。 */
    const hasProjects = computed<boolean>(() => projects.value.length > 0)

    /** 当前页码（从 offset / limit 派生，1-based）。 */
    const currentPage = computed<number>(() =>
      pagination.value.limit > 0
        ? Math.floor(pagination.value.offset / pagination.value.limit) + 1
        : 1,
    )

    /** 总页数。 */
    const totalPages = computed<number>(() =>
      pagination.value.limit > 0
        ? Math.ceil(pagination.value.total / pagination.value.limit)
        : 1,
    )

    /** 当前项目的资源引用数量（优先取 resourceRefs，回退到 currentProject.resource_count）。 */
    const currentResourceCount = computed<number>(() => {
      if (resourceRefs.value.length > 0) return resourceRefs.value.length
      return currentProject.value?.resource_count ?? 0
    })

    /** 同步记录当前页码。 */
    const currentRecordsPage = computed<number>(() =>
      recordsPagination.value.limit > 0
        ? Math.floor(recordsPagination.value.offset / recordsPagination.value.limit) + 1
        : 1,
    )

    /** 同步记录总页数。 */
    const totalRecordsPages = computed<number>(() =>
      recordsPagination.value.limit > 0
        ? Math.ceil(recordsPagination.value.total / recordsPagination.value.limit)
        : 1,
    )

    /** 是否有任何加载操作进行中。 */
    const anyLoading = computed<boolean>(
      () =>
        loading.value ||
        detailLoading.value ||
        statusLoading.value ||
        creating.value ||
        cloning.value ||
        deleting.value ||
        committing.value ||
        pushing.value ||
        pulling.value ||
        refsLoading.value ||
        addingRef.value ||
        removingRef.value ||
        recordsLoading.value,
    )

    // ===== 内部工具 =====

    /**
     * 解包响应信封：后端统一返回 { code, message, data, request_id }，
     * 此处兼容直接返回 payload 的情况。
     */
    function unwrap<T>(response: unknown): T {
      const r = response as { data?: { data?: T } | T; data?: T }
      // axios response.data 即后端响应体；后端响应体的 data 字段为实际 payload
      if (r && typeof r === 'object' && 'data' in r) {
        const body = r.data as { data?: T } | T
        if (body && typeof body === 'object' && 'data' in body) {
          return (body as { data?: T }).data as T
        }
        return body as T
      }
      return response as T
    }

    /** 从项目列表中按 project_id 移除一条（用于删除后本地同步）。 */
    function removeFromList(projectId: string): void {
      projects.value = projects.value.filter(
        (p) => p.project_id !== projectId,
      )
    }

    /** 在项目列表中按 project_id 更新一条（用于 commit/push/pull 后本地同步状态）。 */
    function updateInList(manifest: ProjectSyncManifest): void {
      const idx = projects.value.findIndex(
        (p) => p.project_id === manifest.project_id,
      )
      if (idx >= 0) {
        projects.value[idx] = manifest
      }
    }

    // ===== Actions =====

    /**
     * 分页列出项目（支持状态/作者过滤）.
     * 对应 GET /api/v1/project-sync/projects
     */
    async function fetchProjects(
      params: FetchProjectsParams = {},
    ): Promise<void> {
      loading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.PROJECT_SYNC, '/projects'),
          {
            params: {
              status: params.status,
              author: params.author,
              limit: params.limit ?? 50,
              offset: params.offset ?? 0,
            },
          },
        )
        const payload = unwrap<ListProjectsResponse>(response)
        projects.value = payload.items ?? []
        pagination.value = {
          total: payload.total ?? 0,
          limit: payload.limit ?? 50,
          offset: payload.offset ?? 0,
        }
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取项目列表失败')
        projects.value = []
      } finally {
        loading.value = false
      }
    }

    /**
     * 获取项目详情（含当前状态 + 可选资源引用 / 同步记录）.
     * 对应 GET /api/v1/project-sync/projects/{project_id}
     */
    async function fetchProject(
      projectId: string,
      params: FetchProjectParams = {},
    ): Promise<void> {
      detailLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.PROJECT_SYNC, `/projects/${projectId}`),
          {
            params: {
              include_refs: params.includeRefs ?? true,
              include_records: params.includeRecords ?? false,
            },
          },
        )
        const payload = unwrap<GetProjectResponse>(response)
        currentProject.value = payload
        // 若返回了 resource_refs，则同步刷新本地 resourceRefs
        if (payload.resource_refs) {
          resourceRefs.value = payload.resource_refs
        }
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取项目详情失败')
        currentProject.value = null
      } finally {
        detailLoading.value = false
      }
    }

    /**
     * 创建项目（执行 git init + 写入 .lomo-project.yaml + 可选首 commit）.
     * 对应 POST /api/v1/project-sync/projects
     */
    async function createProject(
      request: CreateProjectRequest,
    ): Promise<ProjectSyncManifest | null> {
      creating.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_SYNC, '/projects'),
          request,
        )
        const payload = unwrap<ProjectSyncManifest>(response)
        lastCreateResult.value = payload
        // 新项目加入列表头部（updated_at 最新）
        projects.value = [payload, ...projects.value]
        pagination.value.total += 1
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '创建项目失败')
        return null
      } finally {
        creating.value = false
      }
    }

    /**
     * 删除项目.
     * 对应 DELETE /api/v1/project-sync/projects/{project_id}?purge_repo={bool}
     *
     * - purge_repo=false（默认）：仅删除 DB 记录，仓库目录保留
     * - purge_repo=true：同时物理删除仓库目录（不可恢复）
     *
     * 删除成功后会从本地列表移除该项目的资源引用与状态。
     */
    async function deleteProject(
      projectId: string,
      purgeRepo: boolean = false,
    ): Promise<DeleteProjectResponse | null> {
      deleting.value = true
      error.value = null
      try {
        const response = await http.delete(
          buildApiPath(API_CONFIG.PROJECT_SYNC, `/projects/${projectId}`),
          { params: { purge_repo: purgeRepo } },
        )
        const payload = unwrap<DeleteProjectResponse>(response)
        lastDeleteResult.value = payload
        removeFromList(projectId)
        if (pagination.value.total > 0) pagination.value.total -= 1
        // 清空当前详情（若被删除的正是 currentProject）
        if (currentProject.value?.project_id === projectId) {
          currentProject.value = null
          projectStatus.value = null
          resourceRefs.value = []
          syncRecords.value = []
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '删除项目失败')
        return null
      } finally {
        deleting.value = false
      }
    }

    /**
     * 查询项目的 Git 状态（执行 git status 推导状态机）.
     * 对应 GET /api/v1/project-sync/projects/{project_id}/status
     */
    async function fetchProjectStatus(projectId: string): Promise<void> {
      statusLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/status`,
          ),
        )
        const payload = unwrap<ProjectStatusResponse>(response)
        projectStatus.value = payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '查询项目状态失败')
        projectStatus.value = null
      } finally {
        statusLoading.value = false
      }
    }

    /**
     * 提交变更（重新计算资源 hash → 更新清单 → git add → git commit）.
     * 对应 POST /api/v1/project-sync/projects/{project_id}/commit
     *
     * 提交成功后会刷新 currentProject 与 projectStatus，并同步更新列表中的状态。
     */
    async function commitProject(
      projectId: string,
      message: string,
    ): Promise<CommitProjectResponse | null> {
      committing.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/commit`,
          ),
          { message },
        )
        const payload = unwrap<CommitProjectResponse>(response)
        lastCommitResult.value = payload
        // 刷新当前项目详情与状态
        await Promise.all([
          fetchProject(projectId, { includeRefs: true }),
          fetchProjectStatus(projectId),
        ])
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '提交变更失败')
        return null
      } finally {
        committing.value = false
      }
    }

    /**
     * 推送到远端仓库（git push origin <branch>）.
     * 对应 POST /api/v1/project-sync/projects/{project_id}/push
     *
     * 要求项目配置了 remote_url，否则后端返回 InvalidProjectStateError。
     */
    async function pushProject(
      projectId: string,
    ): Promise<SyncOperationResponse | null> {
      pushing.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/push`,
          ),
        )
        const payload = unwrap<SyncOperationResponse>(response)
        lastSyncResult.value = payload
        // 推送后刷新状态（ahead 计数应归零）
        await fetchProjectStatus(projectId)
        if (currentProject.value && currentProject.value.project_id === projectId) {
          currentProject.value = {
            ...currentProject.value,
            status: payload.status,
            current_commit: payload.commit_sha || currentProject.value.current_commit,
          }
          updateInList(currentProject.value)
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '推送远端失败')
        return null
      } finally {
        pushing.value = false
      }
    }

    /**
     * 拉取远端更新（git pull origin <branch>）.
     * 对应 POST /api/v1/project-sync/projects/{project_id}/pull
     *
     * 若发生 merge 冲突，状态置为 conflict，由工程师手动解决。
     */
    async function pullProject(
      projectId: string,
    ): Promise<SyncOperationResponse | null> {
      pulling.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/pull`,
          ),
        )
        const payload = unwrap<SyncOperationResponse>(response)
        lastSyncResult.value = payload
        // 拉取后刷新详情与状态（behind 计数应归零，可能引入新文件）
        await Promise.all([
          fetchProject(projectId, { includeRefs: true }),
          fetchProjectStatus(projectId),
        ])
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '拉取远端失败')
        return null
      } finally {
        pulling.value = false
      }
    }

    /**
     * 添加资源引用到项目.
     * 对应 POST /api/v1/project-sync/projects/{project_id}/resources
     *
     * - 校验 resource_type 与 resource_uri scheme 一致（前端契约层已提供 isResourceType）
     * - 同一项目内 resource_uri 唯一
     * - 立即计算 content_hash（hash_computed 标记是否实际计算）
     */
    async function addResourceRef(
      projectId: string,
      request: AddResourceRefRequest,
    ): Promise<AddResourceRefResponse | null> {
      addingRef.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/resources`,
          ),
          request,
        )
        const payload = unwrap<AddResourceRefResponse>(response)
        lastAddRefResult.value = payload
        // 加入本地资源列表
        const exists = resourceRefs.value.some(
          (r) => r.resource_uri === payload.resource_uri,
        )
        if (!exists) {
          resourceRefs.value = [...resourceRefs.value, payload]
        }
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '添加资源引用失败')
        return null
      } finally {
        addingRef.value = false
      }
    }

    /**
     * 列出项目的资源引用（可选按类型过滤）.
     * 对应 GET /api/v1/project-sync/projects/{project_id}/resources?resource_type={type}
     */
    async function fetchResourceRefs(
      projectId: string,
      params: ListResourceRefsParams = {},
    ): Promise<void> {
      refsLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/resources`,
          ),
          { params: { resource_type: params.resource_type } },
        )
        const payload = unwrap<ListResourceRefsResponse>(response)
        resourceRefs.value = payload.items ?? []
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取资源引用列表失败')
        resourceRefs.value = []
      } finally {
        refsLoading.value = false
      }
    }

    /**
     * 删除项目的资源引用（按 resource_uri 精确匹配）.
     * 对应 DELETE /api/v1/project-sync/projects/{project_id}/resources?resource_uri={uri}
     *
     * 注意：resource_uri 是 query 参数（含 "://"），需 encodeURIComponent。
     */
    async function removeResourceRef(
      projectId: string,
      resourceUri: string,
    ): Promise<RemoveResourceRefResponse | null> {
      removingRef.value = true
      error.value = null
      try {
        const response = await http.delete(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/resources`,
          ),
          { params: { resource_uri: resourceUri } },
        )
        const payload = unwrap<RemoveResourceRefResponse>(response)
        lastRemoveRefResult.value = payload
        // 从本地列表移除
        resourceRefs.value = resourceRefs.value.filter(
          (r) => r.resource_uri !== resourceUri,
        )
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '删除资源引用失败')
        return null
      } finally {
        removingRef.value = false
      }
    }

    /**
     * 查询项目的同步记录（按时间倒序）.
     * 对应 GET /api/v1/project-sync/projects/{project_id}/records
     */
    async function fetchSyncRecords(
      projectId: string,
      params: FetchSyncRecordsParams = {},
    ): Promise<void> {
      recordsLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.PROJECT_SYNC,
            `/projects/${projectId}/records`,
          ),
          {
            params: {
              direction: params.direction,
              limit: params.limit ?? 50,
              offset: params.offset ?? 0,
            },
          },
        )
        const payload = unwrap<ListSyncRecordsResponse>(response)
        syncRecords.value = payload.items ?? []
        recordsPagination.value = {
          total: payload.total ?? 0,
          limit: payload.limit ?? 50,
          offset: payload.offset ?? 0,
        }
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '获取同步记录失败')
        syncRecords.value = []
      } finally {
        recordsLoading.value = false
      }
    }

    /**
     * 克隆远端项目（git clone + 注册到 DB）.
     * 对应 POST /api/v1/project-sync/clone
     *
     * 克隆成功后会写入 CLONE SyncRecord，并将新项目加入本地列表。
     */
    async function cloneProject(
      request: CloneProjectRequest,
    ): Promise<ProjectSyncManifest | null> {
      cloning.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_SYNC, '/clone'),
          request,
        )
        const payload = unwrap<ProjectSyncManifest>(response)
        lastCloneResult.value = payload
        // 新项目加入列表头部
        projects.value = [payload, ...projects.value]
        pagination.value.total += 1
        return payload
      } catch (e: unknown) {
        error.value = extractErrorMessage(e, '克隆远端项目失败')
        return null
      } finally {
        cloning.value = false
      }
    }

    // ===== 清理 / 重置 =====

    /**
     * 清空当前项目详情相关的本地状态.
     * 切换项目或退出项目详情页时调用，避免旧数据残留。
     */
    function clearCurrentProject(): void {
      currentProject.value = null
      projectStatus.value = null
      resourceRefs.value = []
      syncRecords.value = []
      recordsPagination.value = { total: 0, limit: 50, offset: 0 }
    }

    /** 重置整个 Store 到初始状态。 */
    function $reset(): void {
      projects.value = []
      currentProject.value = null
      projectStatus.value = null
      resourceRefs.value = []
      syncRecords.value = []
      pagination.value = { total: 0, limit: 50, offset: 0 }
      recordsPagination.value = { total: 0, limit: 50, offset: 0 }
      lastCreateResult.value = null
      lastCloneResult.value = null
      lastCommitResult.value = null
      lastSyncResult.value = null
      lastDeleteResult.value = null
      lastAddRefResult.value = null
      lastRemoveRefResult.value = null
      loading.value = false
      detailLoading.value = false
      statusLoading.value = false
      creating.value = false
      cloning.value = false
      deleting.value = false
      committing.value = false
      pushing.value = false
      pulling.value = false
      refsLoading.value = false
      addingRef.value = false
      removingRef.value = false
      recordsLoading.value = false
      error.value = null
    }

    // ===== 导出 =====
    return {
      // State
      projects,
      currentProject,
      projectStatus,
      resourceRefs,
      syncRecords,
      pagination,
      recordsPagination,
      lastCreateResult,
      lastCloneResult,
      lastCommitResult,
      lastSyncResult,
      lastDeleteResult,
      lastAddRefResult,
      lastRemoveRefResult,
      // Loading
      loading,
      detailLoading,
      statusLoading,
      creating,
      cloning,
      deleting,
      committing,
      pushing,
      pulling,
      refsLoading,
      addingRef,
      removingRef,
      recordsLoading,
      error,
      // Computed
      hasProjects,
      currentPage,
      totalPages,
      currentResourceCount,
      currentRecordsPage,
      totalRecordsPages,
      anyLoading,
      // Actions
      fetchProjects,
      fetchProject,
      createProject,
      deleteProject,
      fetchProjectStatus,
      commitProject,
      pushProject,
      pullProject,
      addResourceRef,
      fetchResourceRefs,
      removeResourceRef,
      fetchSyncRecords,
      cloneProject,
      clearCurrentProject,
      $reset,
    }
  },
)
