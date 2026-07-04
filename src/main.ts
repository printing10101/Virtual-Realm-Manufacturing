// === 全局错误捕获（必须在所有其他代码之前注册） ===
// 用于诊断 Tauri 桌面环境下白屏问题：将任何未捕获的错误渲染到页面，避免白屏无信息。
function renderFatalError(stage: string, err: unknown) {
  const msg = err instanceof Error ? `${err.name}: ${err.message}\n${err.stack ?? ''}` : String(err)
  const html = `
    <div style="position:fixed;inset:0;background:#1e1e1e;color:#ff5555;font-family:Consolas,monospace;font-size:13px;padding:20px;z-index:2147483647;overflow:auto;white-space:pre-wrap;">
      <h2 style="color:#ff9900;margin:0 0 12px;">[致命错误] ${stage}</h2>
      <div style="color:#dddddd;">${msg.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
      <hr style="border:0;border-top:1px solid #444;margin:16px 0;" />
      <div style="color:#888;">UA: ${navigator.userAgent}</div>
      <div style="color:#888;">URL: ${location.href}</div>
      <div style="color:#888;">Time: ${new Date().toISOString()}</div>
    </div>
  `
  // 尝试写入 body；若 body 尚未就绪，写入 html
  const target = document.body || document.documentElement
  // 如果 #app 存在，先清空它再追加错误面板
  const appEl = document.getElementById('app')
  if (appEl) appEl.innerHTML = ''
  const wrapper = document.createElement('div')
  wrapper.innerHTML = html
  target.appendChild(wrapper.firstElementChild as HTMLElement)
}

window.addEventListener('error', (e) => {
  renderFatalError('window.error', e.error ?? `${e.message} @ ${e.filename}:${e.lineno}:${e.colno}`)
})
window.addEventListener('unhandledrejection', (e) => {
  renderFatalError('unhandledrejection', e.reason)
})

// === 正常应用启动流程 ===
import { createApp, ref, watch } from 'vue'
import { createPinia } from 'pinia'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import App from './App.vue'
import router from './router'
import { i18n, setLocale, SUPPORTED_LOCALES, type SupportedLocale } from './i18n'
import { setHttpReady } from './utils/http'
import './assets/styles/theme.css'

function getLocale(): string {
  return localStorage.getItem('app_locale') || 'zh-CN'
}

const elLocale = ref(getLocale() === 'en' ? en : zhCn)

function syncElLocale(locale: string) {
  elLocale.value = locale === 'en' ? en : zhCn
}

watch(() => localStorage.getItem('app_locale'), (val) => {
  if (val) syncElLocale(val)
})

const originalSetLocale = setLocale
function setLocaleWithEl(locale: SupportedLocale) {
  originalSetLocale(locale)
  syncElLocale(locale)
}
(window as Window & { __setLocale?: typeof setLocaleWithEl }).__setLocale = setLocaleWithEl

try {
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)
  app.use(i18n)
  app.provide('locale', elLocale)
  app.use(router)

  app.config.globalProperties.$setLocale = setLocaleWithEl

  app.mount('#app')
  // 通知 index.html 中的诊断脚本：Vue 已挂载，避免误判为白屏
  ;(window as Window & { __markVueMounted__?: () => void }).__markVueMounted__?.()
} catch (err) {
  renderFatalError('Vue mount', err)
  throw err
}

// 初始化阶段完成后启用 HTTP 错误弹窗（延迟 3 秒等待后端健康检查）
setTimeout(() => setHttpReady(), 3000)

// === Tauri 启动动画收尾 ===
// Vue 应用挂载完成、首屏渲染就绪后，关闭原生 splashscreen 窗口并显示主窗口。
// 仅在 Tauri 环境下执行；Web 开发模式下不触发。
async function closeNativeSplashscreen() {
  const isTauri =
    typeof window !== 'undefined' &&
    Boolean((window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__)
  if (!isTauri) return
  try {
    const mod = await import('@tauri-apps/api/core')
    await mod.invoke('close_splashscreen')
  } catch (err) {
    // splashscreen 关闭失败不应阻塞应用启动
    console.warn('[main] 关闭 splashscreen 失败:', err)
  }
}
// 等待一帧让首屏真正绘制后再切换，避免出现短暂白屏
requestAnimationFrame(() => {
  setTimeout(closeNativeSplashscreen, 100)
})
