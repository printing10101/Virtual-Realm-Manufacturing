/**
 * 工作流模板市场 Pinia Store（ADR-010 阶段 6 p6-1）
 *
 * 对接后端 `python/app/api/v1/workflow_templates.py` 9 个端点：
 *   - GET    /api/v1/workflow-templates                     模板列表（分页/过滤/排序）
 *   - GET    /api/v1/workflow-templates/search              关键词搜索
 *   - GET    /api/v1/workflow-templates/stats               市场全局统计
 *   - GET    /api/v1/workflow-templates/{template_id}       模板详情（可选 version）
 *   - GET    /api/v1/workflow-templates/{template_id}/versions   版本列表
 *   - GET    /api/v1/workflow-templates/{template_id}/download   下载（自增计数）
 *   - POST   /api/v1/workflow-templates/publish             发布模板（新模板或新版本）
 *   - POST   /api/v1/workflow-templates/{template_id}/rate       评分（1.0-5.0）
 *   - POST   /api/v1/workflow-templates/{template_id}/unpublish  下架模板（管理员）
 *
 * 设计要点：
 *   1. 模板 = WorkflowSpec + 市场元数据，多版本管理（semver）
 *   2. 市场统计字段（downloads / avg_rating / rating_count）由后端服务层维护
 *   3. 前端通过此 Store 统一访问市场数据，避免组件直接调用 HTTP
 *   4. 错误统一通过 extractErrorMessage 提取，存入 error state
 */
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import http from "@/utils/http";
import { extractErrorMessage } from "@/utils/error-handler";
import { formatDateTimeSafe } from "@/utils/formatters";
import { API_CONFIG, buildApiPath } from "@/config/api";
import {
  type WorkflowTemplateSummary,
  type WorkflowTemplateVersionSummary,
  type ListTemplatesResponse,
  type SearchTemplatesResponse,
  type GetTemplateResponse,
  type ListVersionsResponse,
  type MarketStatsResponse,
  type PublishTemplateRequest,
  type PublishTemplateResponse,
  type RateTemplateResponse,
  type UnpublishTemplateResponse,
  type TemplateCategory,
  type TemplateSortBy,
  TEMPLATE_CATEGORY_LABELS,
} from "@/contracts/workflow_template";

// Store 局部类型（派生 / UI 辅助）

/** 分页信息（从 list 响应派生）。 */
interface PaginationState {
  total: number;
  limit: number;
  offset: number;
}

/** 列表查询参数（与后端 Query 参数对齐）。 */
interface FetchTemplatesParams {
  category?: TemplateCategory;
  tag?: string;
  author?: string;
  limit?: number;
  offset?: number;
  sort_by?: TemplateSortBy;
}

// Store 定义

export const useWorkflowTemplateStore = defineStore("workflowTemplate", () => {
  // State

  /** 模板列表（list 端点返回的 items）。 */
  const templates = ref<WorkflowTemplateSummary[]>([]);
  /** 当前查看的模板详情（含 template / version / manifest 三层）。 */
  const currentTemplate = ref<GetTemplateResponse | null>(null);
  /** 当前模板的版本列表。 */
  const versions = ref<WorkflowTemplateVersionSummary[]>([]);
  /** 搜索结果列表。 */
  const searchResults = ref<WorkflowTemplateSummary[]>([]);
  /** 市场全局统计。 */
  const marketStats = ref<MarketStatsResponse | null>(null);
  /** 分页信息。 */
  const pagination = ref<PaginationState>({
    total: 0,
    limit: 50,
    offset: 0,
  });
  /** 最近一次发布响应（用于 UI 提示）。 */
  const lastPublishResult = ref<PublishTemplateResponse | null>(null);
  /** 最近一次评分响应。 */
  const lastRateResult = ref<RateTemplateResponse | null>(null);
  /** 最近一次下架响应。 */
  const lastUnpublishResult = ref<UnpublishTemplateResponse | null>(null);

  const loading = ref(false);
  const detailLoading = ref(false);
  const versionsLoading = ref(false);
  const searchLoading = ref(false);
  const statsLoading = ref(false);
  const publishing = ref(false);
  const rating = ref(false);
  const unpublishing = ref(false);
  const error = ref<string | null>(null);

  // Computed

  /** 是否有模板数据。 */
  const hasTemplates = computed<boolean>(() => templates.value.length > 0);

  /** 是否有搜索结果。 */
  const hasSearchResults = computed<boolean>(
    () => searchResults.value.length > 0,
  );

  /** 当前页码（从 offset / limit 派生，1-based）。 */
  const currentPage = computed<number>(
    () => Math.floor(pagination.value.offset / pagination.value.limit) + 1,
  );

  /** 总页数。 */
  const totalPages = computed<number>(() =>
    pagination.value.limit > 0
      ? Math.ceil(pagination.value.total / pagination.value.limit)
      : 1,
  );

  /** 是否有任何加载操作进行中。 */
  const anyLoading = computed<boolean>(
    () =>
      loading.value ||
      detailLoading.value ||
      versionsLoading.value ||
      searchLoading.value ||
      statsLoading.value ||
      publishing.value ||
      rating.value ||
      unpublishing.value,
  );

  /** 市场统计格式化（用于 UI 直接展示）。 */
  const marketStatsDisplay = computed(() => ({
    totalTemplates: marketStats.value?.total_templates ?? 0,
    totalDownloads: marketStats.value?.total_downloads ?? 0,
    avgRating: marketStats.value?.avg_rating ?? 0,
  }));

  // Actions

  /**
   * 分页列出模板（支持分类/标签/作者过滤，多种排序）.
   * 对应 GET /api/v1/workflow-templates
   */
  async function fetchTemplates(
    params: FetchTemplatesParams = {},
  ): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const response = await http.get(API_CONFIG.WORKFLOW_TEMPLATES, {
        params: {
          category: params.category,
          tag: params.tag,
          author: params.author,
          limit: params.limit ?? 50,
          offset: params.offset ?? 0,
          sort_by: params.sort_by ?? "downloads",
        },
      });
      const data = response.data?.data ?? response.data;
      const payload = data as ListTemplatesResponse;
      templates.value = payload.items ?? [];
      pagination.value = {
        total: payload.total ?? 0,
        limit: payload.limit ?? 50,
        offset: payload.offset ?? 0,
      };
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "获取工作流模板列表失败");
      templates.value = [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * 关键词搜索模板（name / description / tags / author 模糊匹配）.
   * 对应 GET /api/v1/workflow-templates/search?q={q}&limit={limit}
   */
  async function searchTemplates(q: string, limit: number = 50): Promise<void> {
    searchLoading.value = true;
    error.value = null;
    try {
      const response = await http.get(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, "/search"),
        { params: { q, limit } },
      );
      const data = response.data?.data ?? response.data;
      const payload = data as SearchTemplatesResponse;
      searchResults.value = payload.items ?? [];
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "搜索工作流模板失败");
      searchResults.value = [];
    } finally {
      searchLoading.value = false;
    }
  }

  /**
   * 获取市场全局统计（模板总数 / 总下载 / 平均评分）.
   * 对应 GET /api/v1/workflow-templates/stats
   */
  async function fetchMarketStats(): Promise<void> {
    statsLoading.value = true;
    error.value = null;
    try {
      const response = await http.get(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, "/stats"),
      );
      const data = response.data?.data ?? response.data;
      marketStats.value = data as MarketStatsResponse;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "获取市场统计失败");
      marketStats.value = null;
    } finally {
      statsLoading.value = false;
    }
  }

  /**
   * 获取模板详情（含主表 + 版本 + manifest 三层）.
   * 对应 GET /api/v1/workflow-templates/{template_id}?version={version}
   * @param templateId 模板业务 ID
   * @param version 版本号（可选，None 表示最新版本）
   */
  async function fetchTemplate(
    templateId: string,
    version?: string,
  ): Promise<void> {
    detailLoading.value = true;
    error.value = null;
    try {
      const response = await http.get(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, `/${templateId}`),
        { params: version ? { version } : {} },
      );
      const data = response.data?.data ?? response.data;
      currentTemplate.value = data as GetTemplateResponse;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "获取工作流模板详情失败");
      currentTemplate.value = null;
    } finally {
      detailLoading.value = false;
    }
  }

  /**
   * 列出某模板的所有版本（按创建时间倒序）.
   * 对应 GET /api/v1/workflow-templates/{template_id}/versions
   */
  async function fetchVersions(templateId: string): Promise<void> {
    versionsLoading.value = true;
    error.value = null;
    try {
      const response = await http.get(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, `/${templateId}/versions`),
      );
      const data = response.data?.data ?? response.data;
      const payload = data as ListVersionsResponse;
      versions.value = payload.versions ?? [];
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "获取版本列表失败");
      versions.value = [];
    } finally {
      versionsLoading.value = false;
    }
  }

  /**
   * 下载模板（自增下载计数，返回完整 manifest + spec）.
   * 对应 GET /api/v1/workflow-templates/{template_id}/download?version={version}
   *
   * 下载成功后会同步更新当前列表中对应模板的 downloads 计数（+1），
   * 保证 UI 数据一致性。
   */
  async function downloadTemplate(
    templateId: string,
    version?: string,
  ): Promise<GetTemplateResponse | null> {
    detailLoading.value = true;
    error.value = null;
    try {
      const response = await http.get(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, `/${templateId}/download`),
        { params: version ? { version } : {} },
      );
      const data = response.data?.data ?? response.data;
      const payload = data as GetTemplateResponse;
      currentTemplate.value = payload;
      // 同步更新列表中的下载计数
      const item = templates.value.find((t) => t.template_id === templateId);
      if (item) item.downloads += 1;
      return payload;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "下载工作流模板失败");
      return null;
    } finally {
      detailLoading.value = false;
    }
  }

  /**
   * 发布工作流模板（新模板或新版本）.
   * 对应 POST /api/v1/workflow-templates/publish
   *
   * - 首次发布：创建主表记录 + 版本记录
   * - 已存在：创建新版本记录（version 必须不同于 latest_version）
   *
   * @param request 包含 template_dict（manifest 字典）和可选 changelog
   */
  async function publishTemplate(
    request: PublishTemplateRequest,
  ): Promise<PublishTemplateResponse | null> {
    publishing.value = true;
    error.value = null;
    try {
      const response = await http.post(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, "/publish"),
        request,
      );
      const data = response.data?.data ?? response.data;
      const payload = data as PublishTemplateResponse;
      lastPublishResult.value = payload;
      return payload;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "发布工作流模板失败");
      return null;
    } finally {
      publishing.value = false;
    }
  }

  /**
   * 给模板评分（1.0-5.0），增量更新 avg_rating / rating_count.
   * 对应 POST /api/v1/workflow-templates/{template_id}/rate
   *
   * 评分成功后会同步更新当前列表中对应模板的 avg_rating / rating_count，
   * 保证 UI 数据一致性。
   */
  async function rateTemplate(
    templateId: string,
    ratingValue: number,
  ): Promise<RateTemplateResponse | null> {
    rating.value = true;
    error.value = null;
    try {
      const response = await http.post(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, `/${templateId}/rate`),
        { rating: ratingValue },
      );
      const data = response.data?.data ?? response.data;
      const payload = data as RateTemplateResponse;
      lastRateResult.value = payload;
      // 同步更新列表中的评分
      const item = templates.value.find((t) => t.template_id === templateId);
      if (item) {
        item.avg_rating = payload.avg_rating;
        item.rating_count = payload.rating_count;
      }
      return payload;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "评分失败");
      return null;
    } finally {
      rating.value = false;
    }
  }

  /**
   * 下架模板（status -> unpublished，不删除数据）.
   * 对应 POST /api/v1/workflow-templates/{template_id}/unpublish
   *
   * 下架后模板不再出现在 list/search 结果中，但已发布的版本数据保留。
   * 下架成功后会从本地列表中移除该模板。
   */
  async function unpublishTemplate(
    templateId: string,
  ): Promise<UnpublishTemplateResponse | null> {
    unpublishing.value = true;
    error.value = null;
    try {
      const response = await http.post(
        buildApiPath(API_CONFIG.WORKFLOW_TEMPLATES, `/${templateId}/unpublish`),
      );
      const data = response.data?.data ?? response.data;
      const payload = data as UnpublishTemplateResponse;
      lastUnpublishResult.value = payload;
      // 从本地列表移除
      templates.value = templates.value.filter(
        (t) => t.template_id !== templateId,
      );
      searchResults.value = searchResults.value.filter(
        (t) => t.template_id !== templateId,
      );
      // 清空当前详情
      if (currentTemplate.value?.template.template_id === templateId) {
        currentTemplate.value = null;
      }
      return payload;
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, "下架工作流模板失败");
      return null;
    } finally {
      unpublishing.value = false;
    }
  }

  /**
   * 一次性刷新市场看板数据（列表 + 统计）.
   * 看板初始化时调用。
   */
  async function refreshMarketplace(): Promise<void> {
    await Promise.allSettled([fetchTemplates(), fetchMarketStats()]);
  }

  // Helpers

  /**
   * 格式化时间戳为本地时间字符串。
   * @param ts ISO 8601 字符串
   */
  const formatTime = (ts: string | null | undefined): string =>
    formatDateTimeSafe(ts);

  /**
   * 格式化评分（保留 1 位小数 + 星标）。
   * @param value 0-5 的评分
   */
  function formatRating(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value))
      return "-";
    return `${value.toFixed(1)} ★`;
  }

  /**
   * 格式化下载量（千分位）。
   * @param value 下载次数
   */
  function formatDownloads(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value))
      return "0";
    return value.toLocaleString("zh-CN");
  }

  /**
   * 获取分类中文标签。
   * @param category 模板分类
   */
  function categoryLabel(category: TemplateCategory | string): string {
    return TEMPLATE_CATEGORY_LABELS[category as TemplateCategory] ?? category;
  }

  /**
   * 重置 Store 到初始状态。
   */
  function reset(): void {
    templates.value = [];
    currentTemplate.value = null;
    versions.value = [];
    searchResults.value = [];
    marketStats.value = null;
    pagination.value = { total: 0, limit: 50, offset: 0 };
    lastPublishResult.value = null;
    lastRateResult.value = null;
    lastUnpublishResult.value = null;
    error.value = null;
  }

  return {
    // state
    templates,
    currentTemplate,
    versions,
    searchResults,
    marketStats,
    pagination,
    lastPublishResult,
    lastRateResult,
    lastUnpublishResult,
    loading,
    detailLoading,
    versionsLoading,
    searchLoading,
    statsLoading,
    publishing,
    rating,
    unpublishing,
    error,
    // computed
    hasTemplates,
    hasSearchResults,
    currentPage,
    totalPages,
    anyLoading,
    marketStatsDisplay,
    // actions
    fetchTemplates,
    searchTemplates,
    fetchMarketStats,
    fetchTemplate,
    fetchVersions,
    downloadTemplate,
    publishTemplate,
    rateTemplate,
    unpublishTemplate,
    refreshMarketplace,
    // helpers
    formatTime,
    formatRating,
    formatDownloads,
    categoryLabel,
    reset,
  };
});
