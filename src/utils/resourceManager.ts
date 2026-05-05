type ResourceType = 'timer' | 'interval' | 'event' | 'customEvent' | 'connection' | 'echarts' | 'observer'

interface ResourceEntry {
  id: string
  type: ResourceType
  cleanup: () => void
  createdAt: number
  metadata?: Record<string, any>
}

class ResourceManager {
  private resources: Map<string, ResourceEntry> = new Map()
  private warningThreshold: number = 50

  register(type: ResourceType, cleanup: () => void, metadata?: Record<string, any>): string {
    const id = `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const entry: ResourceEntry = {
      id,
      type,
      cleanup,
      createdAt: Date.now(),
      metadata
    }
    this.resources.set(id, entry)

    if (this.resources.size > this.warningThreshold) {
      console.warn(`[ResourceManager] High resource count: ${this.resources.size}. Possible memory leak detected.`)
    }

    return id
  }

  unregister(id: string): boolean {
    const entry = this.resources.get(id)
    if (entry) {
      entry.cleanup()
      this.resources.delete(id)
      return true
    }
    return false
  }

  registerTimeout(fn: () => void, delay: number): string {
    const timerId = setTimeout(() => {
      fn()
      this.resources.delete(id)
    }, delay) as unknown as number
    const id = this.register('timer', () => clearTimeout(timerId), { delay })
    return id
  }

  registerInterval(fn: () => void, interval: number): string {
    const timerId = setInterval(fn, interval) as unknown as number
    return this.register('interval', () => clearInterval(timerId), { interval })
  }

  registerEventListener(
    target: EventTarget,
    event: string,
    handler: EventListenerOrEventListenerObject,
    options?: boolean | AddEventListenerOptions
  ): string {
    target.addEventListener(event, handler, options)
    return this.register('event', () => {
      target.removeEventListener(event, handler, options)
    }, { target: target.constructor.name, event })
  }

  registerConnection(closeFn: () => void, metadata?: Record<string, any>): string {
    return this.register('connection', closeFn, metadata)
  }

  registerECharts(disposeFn: () => void, metadata?: Record<string, any>): string {
    return this.register('echarts', disposeFn, metadata)
  }

  cleanup(type?: ResourceType): void {
    const entries = Array.from(this.resources.entries())
    for (const [id, entry] of entries) {
      if (!type || entry.type === type) {
        try {
          entry.cleanup()
        } catch (e) {
          console.error(`[ResourceManager] Error cleaning up resource ${id}:`, e)
        }
        this.resources.delete(id)
      }
    }
  }

  cleanupAll(): void {
    this.cleanup()
  }

  getCount(type?: ResourceType): number {
    if (!type) return this.resources.size
    return Array.from(this.resources.values()).filter(r => r.type === type).length
  }

  getStats(): Record<string, number> {
    const stats: Record<string, number> = {}
    for (const entry of this.resources.values()) {
      stats[entry.type] = (stats[entry.type] || 0) + 1
    }
    return stats
  }

  getLeakedResources(): ResourceEntry[] {
    const now = Date.now()
    const oneMinute = 60 * 1000
    return Array.from(this.resources.values()).filter(
      r => now - r.createdAt > oneMinute
    )
  }

  setWarningThreshold(threshold: number): void {
    this.warningThreshold = threshold
  }
}

export const resourceManager = new ResourceManager()

export function createResourceManager(): ResourceManager {
  return new ResourceManager()
}

export type { ResourceType, ResourceEntry }
