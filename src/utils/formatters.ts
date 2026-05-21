/**
 * 统一格式化工具函数
 */

/**
 * 格式化时间戳为本地化字符串
 * @param ts - 时间戳（毫秒）
 * @param locale - 语言环境，默认 'zh-CN'
 * @returns 格式化后的日期时间字符串
 */
export function formatTimestamp(ts: number, locale: string = 'zh-CN'): string {
  const localeTag = locale === 'en' ? 'en-US' : 'zh-CN'
  return new Date(ts).toLocaleString(localeTag)
}

/**
 * 格式化秒级时间戳为本地化字符串
 * @param ts - 时间戳（秒）
 * @param locale - 语言环境
 * @param options - Intl.DateTimeFormatOptions
 * @returns 格式化后的日期时间字符串
 */
export function formatSecondsTimestamp(
  ts: number | null | undefined,
  locale: string = 'zh-CN',
  options?: Intl.DateTimeFormatOptions
): string {
  if (ts == null) return ''
  const localeTag = locale === 'en' ? 'en-US' : 'zh-CN'
  return new Date(ts * 1000).toLocaleString(localeTag, options)
}

/**
 * 格式化日期字符串为本地化字符串
 * @param iso - ISO格式日期字符串
 * @param locale - 语言环境
 * @returns 格式化后的日期时间字符串
 */
export function formatDate(iso: string | null | undefined, locale: string = 'zh-CN'): string {
  if (!iso) return ''
  const localeTag = locale === 'en' ? 'en-US' : 'zh-CN'
  return new Date(iso).toLocaleString(localeTag, { hour12: false })
}

/**
 * 格式化文件大小
 * @param bytes - 字节数
 * @returns 格式化后的文件大小字符串
 */
export function formatFileSize(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let s = bytes
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++ }
  return s.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

/**
 * 格式化时长（秒 → 人类可读）
 * @param seconds - 秒数
 * @param short - 是否使用简写格式（如 2h 30m）
 * @returns 格式化后的时长字符串
 */
export function formatDuration(seconds: number, short = false): string {
  if (!seconds) return '0' + (short ? 'm' : '分钟')
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return short ? `${hours}h ${minutes}m` : `${hours}小时${minutes}分钟`
  }
  return `${minutes}` + (short ? 'm' : '分钟')
}
