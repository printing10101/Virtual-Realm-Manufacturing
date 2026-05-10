import { createI18n } from 'vue-i18n'
import messages from '@/locales/lod.json'

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: messages as any,
})

export default i18n
