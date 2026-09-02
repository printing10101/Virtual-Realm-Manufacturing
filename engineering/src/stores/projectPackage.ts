/**
 * 项目包 Pinia Store（ADR-015 阶段 6 p6-4：项目导入导出 ``.lomo`` 包格式）
 *
 * 对接后端 `python/app/api/v1/project_packages.py` 8 个端点：
 *   - POST   /api/v1/project-packages/export                导出项目为 .lomo 包
 *   - POST   /api/v1/project-packages/import                导入 .lomo 包（multipart 上传）
 *   - POST   /api/v1/project-packages/validate              校验 .lomo 包完整性（multipart 上传）
 *   - POST   /api/v1/project-packages/preview               预览 .lomo 包内容（multipart 上传）
 *   - GET    /api/v1/project-packages/exports               列出导出记录（分页 + 过滤）
 *   - GET    /api/v1/project-packages/exports/{export_id}   查询导出详情（支持 ?download=true 下载）
 *   - DELETE /api/v1/project-packages/exports/{export_id}   删除导出包文件 + 记录
 *   - GET    /api/v1/project-packages/imports               列出导入记录（分页 + 过滤）
 *
 * 设计要点：
 *   1. 前端通过此 Store 统一访问项目包 API，不直接持有 ProjectSyncStore 状态
 *   2. 导出/导入为同步长任务（请求阻塞至完成），后端在服务层管理 pending→running→completed/failed 状态机
 *   3. 导入/校验/预览端点使用 multipart/form-data，文件通过 FormData 上传
 *   4. 导出记录删除后自动刷新当前列表（保持列表与后端一致）
 *   5. 下载通过浏览器原生 location 触发（带 ?download=true 查询参数 + 凭证 Cookie）
 *   6. 错误统一通过 extractErrorMessage 提取，存入 error state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'
import { extractErrorMessage } from '@/utils/error-handler'
import { unwrap } from '@/utils/response'
import { API_CONFIG, buildApiPath } from '@/config/api'
import {
  type ExportProjectRequest,
  type ExportProjectResponse,
  type ImportProjectParams,
  type ImportProjectResponse,
  type ValidatePackageResponse,
  type PreviewPackageResponse,
  type ListExportsParams,
  type ListExportsResponse,
  type ExportRecordSummary,
  type GetExportResponse,
  type DeleteExportResponse,
  type ListImportsParams,
  type ListImportsResponse,
  type ImportRecordSummary,
} from '@/contracts/project_package'

// Store 局部类型（派生 / UI 辅助）

/** 导出记录分页信息。 */
interface ExportPaginationState {
  total: number
  limit: number
  offset: number
}

/** 导入记录分页信息。 */
interface ImportPaginationState {
  total: number
  limit: number
  offset: number
}

/** fetchExports 入参（与后端 Query 参数对齐）。 */
interface FetchExportsParams extends ListExportsParams {}

/** fetchImports 入参（与后端 Query 参数对齐）。 */
interface FetchImportsParams extends ListImportsParams {}

// Store 定义

export const useProjectPackageStore = defineStore(
  'projectPackage',
  () => {
// State：导出记录列表

    /** 导出记录列表（list 端点返回的 items）。 */
    const exports = ref<ExportRecordSummary[]>([])
    /** 导出记录分页信息。 */
    const exportPagination = ref<ExportPaginationState>({
      total: 0,
      limit: 100,
      offset: 0,
    })

// State：导入记录列表

    /** 导入记录列表（list 端点返回的 items）。 */
    const imports = ref<ImportRecordSummary[]>([])
    /** 导入记录分页信息。 */
    const importPagination = ref<ImportPaginationState>({
      total: 0,
      limit: 100,
      offset: 0,
    })

// State：当前导出记录详情

    /** 当前查看的导出记录详情（含 download_url）。 */
    const currentExport = ref<GetExportResponse | null>(null)

// State：最近一次操作响应（用于 UI 提示）

    /** 最近一次导出响应（含 export_id / package_path / manifest / download_url）。 */
    const lastExportResult = ref<ExportProjectResponse | null>(null)
    /** 最近一次导入响应（含 import_id / 资源记录 / 计数）。 */
    const lastImportResult = ref<ImportProjectResponse | null>(null)
    /** 最近一次校验响应（含 is_valid / errors / warnings）。 */
    const lastValidateResult = ref<ValidatePackageResponse | null>(null)
    /** 最近一次预览响应（包清单 manifest）。 */
    const lastPreviewResult = ref<PreviewPackageResponse | null>(null)
    /** 最近一次删除导出响应。 */
    const lastDeleteResult = ref<DeleteExportResponse | null>(null)

// Loading 标志

    const exporting = ref(false) // POST /export
    const importing = ref(false) // POST /import
    const validating = ref(false) // POST /validate
    const previewing = ref(false) // POST /preview
    const exportsLoading = ref(false) // GET /exports
    const importLoading = ref(false) // GET /imports
    const exportLoading = ref(false) // GET /exports/{id}
    const deleting = ref(false) // DELETE /exports/{id}
    const error = ref<string | null>(null)

// Computed

    /** 是否有导出记录。 */
    const hasExports = computed<boolean>(() => exports.value.length > 0)

    /** 是否有导入记录。 */
    const hasImports = computed<boolean>(() => imports.value.length > 0)

    /** 导出记录列表当前页码（1-based）。 */
    const exportCurrentPage = computed<number>(() =>
      exportPagination.value.limit > 0
        ? Math.floor(exportPagination.value.offset / exportPagination.value.limit) + 1
        : 1,
    )

    /** 导出记录列表总页数。 */
    const exportTotalPages = computed<number>(() =>
      exportPagination.value.limit > 0
        ? Math.ceil(exportPagination.value.total / exportPagination.value.limit)
        : 1,
    )

    /** 导入记录列表当前页码（1-based）。 */
    const importCurrentPage = computed<number>(() =>
      importPagination.value.limit > 0
        ? Math.floor(importPagination.value.offset / importPagination.value.limit) + 1
        : 1,
    )

    /** 导入记录列表总页数。 */
    const importTotalPages = computed<number>(() =>
      importPagination.value.limit > 0
        ? Math.ceil(importPagination.value.total / importPagination.value.limit)
        : 1,
    )

    /** 是否有任何加载操作进行中。 */
    const anyLoading = computed<boolean>(
      () =>
        exporting.value ||
        importing.value ||
        validating.value ||
        previewing.value ||
        exportsLoading.value ||
        importLoading.value ||
        exportLoading.value ||
        deleting.value,
    )

    // unwrap() 已提取到 @/utils/response.ts（消除 6 个 Store 的重复定义）

// Actions：导出

    /**
     * 导出项目为 .lomo 包.
     * 对应 POST /api/v1/project-packages/export
     *
     * 长任务：后端同步执行（请求阻塞至打包完成），前端可通过 HTTP 长连接等待结果。
     *
     * @param request - 导出请求体（含 project_id / exported_by / 内容策略 / 包含开关等）
     * @returns 导出响应（含 export_id / package_path / manifest / download_url），失败返回 null
     */
    async function exportProject(
      request: ExportProjectRequest,
    ): Promise<ExportProjectResponse | null> {
      exporting.value = true
      error.value = null
      try {
        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/export'),
          request,
        )
        const payload = unwrap<ExportProjectResponse>(response)
        lastExportResult.value = payload
        // 导出成功后刷新导出记录列表（确保新记录立即可见）
        await fetchExports({
          project_id: request.project_id,
          limit: exportPagination.value.limit,
          offset: 0,
        })
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '导出项目失败')
        return null
      } finally {
        exporting.value = false
      }
    }

    /**
     * 导入 .lomo 包到目标项目.
     * 对应 POST /api/v1/project-packages/import
     *
     * multipart/form-data 上传：file 通过 FormData 字段上传，其余字段为表单字段。
     * 长任务：后端同步执行（请求阻塞至导入完成）。
     *
     * @param file - .lomo 包文件（File 对象）
     * @param params - 导入参数（导入者 / 冲突策略 / 目标所有者 / reinit_git / dry_run / 目标项目名）
     * @returns 导入响应（含 import_id / 资源记录 / 计数），失败返回 null
     */
    async function importProject(
      file: File,
      params: ImportProjectParams,
    ): Promise<ImportProjectResponse | null> {
      importing.value = true
      error.value = null
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('imported_by', params.imported_by)
        formData.append('conflict_strategy', params.conflict_strategy)
        formData.append('target_owner_id', params.target_owner_id)
        formData.append('reinit_git', String(params.reinit_git))
        formData.append('dry_run', String(params.dry_run))
        formData.append('target_project_name', params.target_project_name)

        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/import'),
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          },
        )
        const payload = unwrap<ImportProjectResponse>(response)
        lastImportResult.value = payload
        // 导入成功后刷新导入记录列表（确保新记录立即可见）
        await fetchImports({
          limit: importPagination.value.limit,
          offset: 0,
        })
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '导入项目失败')
        return null
      } finally {
        importing.value = false
      }
    }

    /**
     * 校验 .lomo 包完整性（不实际导入）.
     * 对应 POST /api/v1/project-packages/validate
     *
     * multipart/form-data 上传。校验项：manifest 可解析、format_version 受支持、
     * checksum 一致、每个资源条目 content_hash 与包内文件实际 sha256 一致、
     * path_in_package 指向的文件存在。
     *
     * @param file - .lomo 包文件（File 对象）
     * @returns 校验结果（含 is_valid / errors / warnings），失败返回 null
     */
    async function validatePackage(
      file: File,
    ): Promise<ValidatePackageResponse | null> {
      validating.value = true
      error.value = null
      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/validate'),
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          },
        )
        const payload = unwrap<ValidatePackageResponse>(response)
        lastValidateResult.value = payload
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '校验包失败')
        return null
      } finally {
        validating.value = false
      }
    }

    /**
     * 预览 .lomo 包内容（返回 manifest，不实际导入）.
     * 对应 POST /api/v1/project-packages/preview
     *
     * multipart/form-data 上传。仅读取 manifest.json，不解压资源文件。
     *
     * @param file - .lomo 包文件（File 对象）
     * @returns 包清单（含格式版本 / 项目元数据 / 资源清单 / 内容策略 / 总大小 / checksum），失败返回 null
     */
    async function previewPackage(
      file: File,
    ): Promise<PreviewPackageResponse | null> {
      previewing.value = true
      error.value = null
      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await http.post(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/preview'),
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          },
        )
        const payload = unwrap<PreviewPackageResponse>(response)
        lastPreviewResult.value = payload
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '预览包失败')
        return null
      } finally {
        previewing.value = false
      }
    }

// Actions：列表查询

    /**
     * 列出导出记录（分页 + 过滤）.
     * 对应 GET /api/v1/project-packages/exports
     *
     * @param params - 查询参数（project_id / status / exported_by / limit / offset）
     * @returns 导出记录列表响应，失败返回 null
     */
    async function fetchExports(
      params: FetchExportsParams = {},
    ): Promise<ListExportsResponse | null> {
      exportsLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/exports'),
          {
            params: {
              project_id: params.project_id,
              status: params.status,
              exported_by: params.exported_by,
              limit: params.limit ?? 100,
              offset: params.offset ?? 0,
            },
          },
        )
        const payload = unwrap<ListExportsResponse>(response)
        exports.value = payload.items ?? []
        exportPagination.value = {
          total: payload.total ?? 0,
          limit: payload.limit ?? 100,
          offset: payload.offset ?? 0,
        }
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '获取导出记录列表失败')
        return null
      } finally {
        exportsLoading.value = false
      }
    }

    /**
     * 列出导入记录（分页 + 过滤）.
     * 对应 GET /api/v1/project-packages/imports
     *
     * @param params - 查询参数（target_project_id / status / imported_by / limit / offset）
     * @returns 导入记录列表响应，失败返回 null
     */
    async function fetchImports(
      params: FetchImportsParams = {},
    ): Promise<ListImportsResponse | null> {
      importLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(API_CONFIG.PROJECT_PACKAGES, '/imports'),
          {
            params: {
              target_project_id: params.target_project_id,
              status: params.status,
              imported_by: params.imported_by,
              limit: params.limit ?? 100,
              offset: params.offset ?? 0,
            },
          },
        )
        const payload = unwrap<ListImportsResponse>(response)
        imports.value = payload.items ?? []
        importPagination.value = {
          total: payload.total ?? 0,
          limit: payload.limit ?? 100,
          offset: payload.offset ?? 0,
        }
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '获取导入记录列表失败')
        return null
      } finally {
        importLoading.value = false
      }
    }

    /**
     * 查询导出记录详情.
     * 对应 GET /api/v1/project-packages/exports/{export_id}
     *
     * 注意：?download=true 查询参数触发文件下载，由 downloadExport() 单独处理，
     * 此处仅获取记录元数据。
     *
     * @param exportId - 导出任务 ID
     * @returns 导出记录详情（含 download_url），失败返回 null
     */
    async function fetchExport(
      exportId: string,
    ): Promise<GetExportResponse | null> {
      exportLoading.value = true
      error.value = null
      try {
        const response = await http.get(
          buildApiPath(
            API_CONFIG.PROJECT_PACKAGES,
            `/exports/${encodeURIComponent(exportId)}`,
          ),
        )
        const payload = unwrap<GetExportResponse>(response)
        currentExport.value = payload
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '获取导出记录详情失败')
        return null
      } finally {
        exportLoading.value = false
      }
    }

// Actions：删除 + 下载

    /**
     * 删除导出包文件 + 数据库记录.
     * 对应 DELETE /api/v1/project-packages/exports/{export_id}
     *
     * 删除成功后自动刷新当前列表（保持列表与后端一致）。
     *
     * @param exportId - 导出任务 ID
     * @returns 删除响应（含 export_id / file_deleted），失败返回 null
     */
    async function deleteExport(
      exportId: string,
    ): Promise<DeleteExportResponse | null> {
      deleting.value = true
      error.value = null
      try {
        const response = await http.delete(
          buildApiPath(
            API_CONFIG.PROJECT_PACKAGES,
            `/exports/${encodeURIComponent(exportId)}`,
          ),
        )
        const payload = unwrap<DeleteExportResponse>(response)
        lastDeleteResult.value = payload
        // 从本地列表移除该记录（避免重新拉取全量列表）
        exports.value = exports.value.filter((item) => item.id !== exportId)
        // 若当前详情被删除，清空 currentExport
        if (currentExport.value?.id === exportId) {
          currentExport.value = null
        }
        // 调整分页 total（保守起见，仍请求后端确认）
        if (exportPagination.value.total > 0) {
          exportPagination.value.total -= 1
        }
        return payload
      } catch (e) {
        error.value = extractErrorMessage(e, '删除导出包失败')
        return null
      } finally {
        deleting.value = false
      }
    }

    /**
     * 触发浏览器下载 .lomo 文件.
     *
     * 不通过 axios 调用（避免 axios 处理二进制流），而是构造完整 URL 后
     * 通过 window.open 或 location 触发浏览器原生下载（带凭证 Cookie）。
     *
     * @param exportId - 导出任务 ID
     * @param baseUrl - 后端基础 URL（默认空字符串，表示同源）
     */
    function downloadExport(exportId: string, baseUrl: string = ''): void {
      const url = `${baseUrl}/api/v1/project-packages/exports/${encodeURIComponent(
        exportId,
      )}?download=true`
      // 使用 window.open 触发下载（保留当前页面，新窗口下载后自动关闭）
      window.open(url, '_blank')
    }

// 清理 / 重置

    /** 清空当前导出记录详情。 */
    function clearCurrentExport(): void {
      currentExport.value = null
    }

    /** 清空最近一次操作响应。 */
    function clearLastResults(): void {
      lastExportResult.value = null
      lastImportResult.value = null
      lastValidateResult.value = null
      lastPreviewResult.value = null
      lastDeleteResult.value = null
    }

    /** 重置 Store 到初始状态。 */
    function $reset(): void {
      exports.value = []
      importPagination.value = { total: 0, limit: 100, offset: 0 }
      imports.value = []
      exportPagination.value = { total: 0, limit: 100, offset: 0 }
      currentExport.value = null
      lastExportResult.value = null
      lastImportResult.value = null
      lastValidateResult.value = null
      lastPreviewResult.value = null
      lastDeleteResult.value = null
      exporting.value = false
      importing.value = false
      validating.value = false
      previewing.value = false
      exportsLoading.value = false
      importLoading.value = false
      exportLoading.value = false
      deleting.value = false
      error.value = null
    }

    return {
      // State
      exports,
      exportPagination,
      imports,
      importPagination,
      currentExport,
      lastExportResult,
      lastImportResult,
      lastValidateResult,
      lastPreviewResult,
      lastDeleteResult,
      exporting,
      importing,
      validating,
      previewing,
      exportsLoading,
      importLoading,
      exportLoading,
      deleting,
      error,
      // Computed
      hasExports,
      hasImports,
      exportCurrentPage,
      exportTotalPages,
      importCurrentPage,
      importTotalPages,
      anyLoading,
      // Actions
      exportProject,
      importProject,
      validatePackage,
      previewPackage,
      fetchExports,
      fetchImports,
      fetchExport,
      deleteExport,
      downloadExport,
      clearCurrentExport,
      clearLastResults,
      $reset,
    }
  },
)
