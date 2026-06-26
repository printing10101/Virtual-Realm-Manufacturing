// ============================================================
// lingjing-manufacturing-ui-v2 / api-config.js
// 集中管理所有前端页面的 API 配置与请求工具函数
// ============================================================

const API_BASE = 'http://localhost:8765';

/**
 * 通用请求封装
 * @param {string} method  HTTP 方法
 * @param {string} path    请求路径（不含 baseUrl）
 * @param {object|null} body 请求体（GET/DELETE 时传 null）
 * @returns {Promise<any>}  后端 data 字段；出错时返回 null
 */
async function request(method, path, body = null) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      console.error(`[API] ${method} ${path} -> HTTP ${response.status}`);
      return null;
    }
    const json = await response.json();
    if (json.code !== 0) {
      console.error(`[API] ${method} ${path} -> 业务错误 code=${json.code} message=${json.message}`);
      return null;
    }
    return json.data;
  } catch (err) {
    console.error(`[API] ${method} ${path} -> 请求失败`, err);
    return null;
  }
}

/** GET 请求，返回 response.data */
async function apiGet(path) {
  return request('GET', path);
}

/** POST 请求，发送 JSON body，返回 response.data */
async function apiPost(path, body) {
  return request('POST', path, body);
}

/** PUT 请求，发送 JSON body，返回 response.data */
async function apiPut(path, body) {
  return request('PUT', path, body);
}

/** DELETE 请求，返回 response.data */
async function apiDelete(path) {
  return request('DELETE', path);
}

/**
 * 将中文状态字符串映射为带颜色的 HTML 徽标
 * 使用奶油白/米色主题配色
 *
 * @param {string} status 状态文本
 * @returns {string} <span> HTML
 */
function formatStatus(status) {
  const map = {
    '运行中':   { bg: '#e8f5e9', color: '#2e7d32' },
    '已完成':   { bg: '#e3f2fd', color: '#1565c0' },
    '待处理':   { bg: '#fff8e1', color: '#f57f17' },
    '已暂停':   { bg: '#fce4ec', color: '#c62828' },
    '已取消':   { bg: '#f3e5f5', color: '#6a1b9a' },
    '进行中':   { bg: '#e8f5e9', color: '#2e7d32' },
    '已入库':   { bg: '#e3f2fd', color: '#1565c0' },
    '生产中':   { bg: '#e0f2f1', color: '#00695c' },
    '已发货':   { bg: '#e8eaf6', color: '#283593' },
    '异常':     { bg: '#ffebee', color: '#b71c1c' },
    '空闲':     { bg: '#fafafa', color: '#616161' },
    '维护中':   { bg: '#fff3e0', color: '#e65100' },
  };

  const style = map[status] || { bg: '#fafafa', color: '#616161' };
  return `<span style="
    display:inline-block;
    padding:2px 10px;
    border-radius:10px;
    font-size:12px;
    line-height:1.6;
    background:${style.bg};
    color:${style.color};
    font-weight:500;
  ">${status}</span>`;
}
