import { createApp, ref, watch } from 'vue'
import { createPinia } from 'pinia'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import App from './App.vue'
import router from './router'
import { i18n, setLocale, SUPPORTED_LOCALES, type SupportedLocale } from './i18n'
import { setHttpReady } from './utils/http'
import './assets/styles/theme.css'

const elLocale = ref(getLocale() === 'en' ? en : zhCn)

function getLocale(): string {
  return localStorage.getItem('app_locale') || 'zh-CN'
}

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

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(i18n)
app.provide('locale', elLocale)
app.use(router)

app.config.globalProperties.$setLocale = setLocaleWithEl

app.mount('#app')

// 初始化阶段完成后启用 HTTP 错误弹窗（延迟 3 秒等待后端健康检查）
setTimeout(() => setHttpReady(), 3000)
