import axios from 'axios'
import { invoke } from '@tauri-apps/api/core'
import { DEFAULT_URLS } from '@/constants'
import { getRequestMerger, destroyRequestMerger } from '@/services/requestMerger'

export interface BenchmarkResult {
  test_name: string
  method: string
  endpoint: string
  total_requests: number
  successful: number
  failed: number
  min_ms: number
  max_ms: number
  avg_ms: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  timestamps_ms: number[]
}

export interface BenchmarkReport {
  results: BenchmarkResult[]
  summary: {
    direct_total_ms: number
    proxy_total_ms: number
    improvement_ms: number
    improvement_percent: number
  }
}

async function measureLatency(
  fn: () => Promise<any>,
  iterations: number
): Promise<number[]> {
  const latencies: number[] = []

  for (let i = 0; i < iterations; i++) {
    const start = performance.now()
    try {
      await fn()
      latencies.push(performance.now() - start)
    } catch {
      latencies.push(-1)
    }
  }

  return latencies
}

function calculatePercentiles(timestamps: number[]): {
  min: number
  max: number
  avg: number
  p50: number
  p95: number
  p99: number
} {
  const valid = timestamps.filter((t) => t > 0).sort((a, b) => a - b)

  if (valid.length === 0) {
    return { min: 0, max: 0, avg: 0, p50: 0, p95: 0, p99: 0 }
  }

  const min = valid[0]
  const max = valid[valid.length - 1]
  const avg = valid.reduce((a, b) => a + b, 0) / valid.length

  const percentile = (p: number) => {
    const index = Math.floor((p / 100) * valid.length)
    return valid[Math.min(index, valid.length - 1)]
  }

  return {
    min,
    max,
    avg,
    p50: percentile(50),
    p95: percentile(95),
    p99: percentile(99),
  }
}

async function benchmarkDirectHttp(
  baseUrl: string,
  endpoint: string,
  method: string,
  iterations: number
): Promise<number[]> {
  return measureLatency(async () => {
    await axios({
      url: `${baseUrl}${endpoint}`,
      method,
      timeout: 10000,
    })
  }, iterations)
}

async function benchmarkProxy(
  baseUrl: string,
  endpoint: string,
  method: string,
  iterations: number
): Promise<number[]> {
  return measureLatency(async () => {
    await invoke('proxy_http_request', {
      request: {
        method,
        url: `${baseUrl}${endpoint}`,
        timeout_ms: 10000,
      },
    })
  }, iterations)
}

async function benchmarkMergedRequests(
  baseUrl: string,
  endpoints: string[],
  method: string,
  iterations: number
): Promise<number[]> {
  const latencies: number[] = []

  for (let i = 0; i < iterations; i++) {
    const start = performance.now()
    try {
      const promises = endpoints.map((endpoint) =>
        getRequestMerger().enqueue({
          method,
          url: `${baseUrl}${endpoint}`,
          timeout_ms: 10000,
        })
      )
      await Promise.all(promises)
      latencies.push(performance.now() - start)
    } catch {
      latencies.push(-1)
    }
  }

  return latencies
}

export async function runBenchmark(
  baseUrl: string = DEFAULT_URLS.PYTHON_BACKEND,
  iterations: number = 20
): Promise<BenchmarkReport> {
  const testEndpoints = [
    { method: 'GET', endpoint: '/health' },
    { method: 'GET', endpoint: '/api/ai/status' },
    { method: 'POST', endpoint: '/api/v1/tasks' },
  ]

  const results: BenchmarkResult[] = []

  for (const { method, endpoint } of testEndpoints) {
    const directLatencies = await benchmarkDirectHttp(
      baseUrl,
      endpoint,
      method,
      iterations
    )

    const proxyLatencies = await benchmarkProxy(
      baseUrl,
      endpoint,
      method,
      iterations
    )

    const directStats = calculatePercentiles(directLatencies)
    const proxyStats = calculatePercentiles(proxyLatencies)

    results.push(
      {
        test_name: `direct_${method}_${endpoint}`,
        method,
        endpoint,
        total_requests: iterations,
        successful: directLatencies.filter((t) => t > 0).length,
        failed: directLatencies.filter((t) => t <= 0).length,
        min_ms: directStats.min,
        max_ms: directStats.max,
        avg_ms: directStats.avg,
        p50_ms: directStats.p50,
        p95_ms: directStats.p95,
        p99_ms: directStats.p99,
        timestamps_ms: directLatencies,
      },
      {
        test_name: `proxy_${method}_${endpoint}`,
        method,
        endpoint,
        total_requests: iterations,
        successful: proxyLatencies.filter((t) => t > 0).length,
        failed: proxyLatencies.filter((t) => t <= 0).length,
        min_ms: proxyStats.min,
        max_ms: proxyStats.max,
        avg_ms: proxyStats.avg,
        p50_ms: proxyStats.p50,
        p95_ms: proxyStats.p95,
        p99_ms: proxyStats.p99,
        timestamps_ms: proxyLatencies,
      }
    )
  }

  const mergedEndpoints = ['/health', '/api/ai/status', '/api/v1/tasks']
  const mergedLatencies = await benchmarkMergedRequests(
    baseUrl,
    mergedEndpoints,
    'GET',
    10
  )
  const mergedStats = calculatePercentiles(mergedLatencies)

  results.push({
    test_name: 'merged_requests_batch',
    method: 'GET',
    endpoint: 'multiple',
    total_requests: mergedEndpoints.length * 10,
    successful: mergedLatencies.filter((t) => t > 0).length * mergedEndpoints.length,
    failed: mergedLatencies.filter((t) => t <= 0).length * mergedEndpoints.length,
    min_ms: mergedStats.min,
    max_ms: mergedStats.max,
    avg_ms: mergedStats.avg,
    p50_ms: mergedStats.p50,
    p95_ms: mergedStats.p95,
    p99_ms: mergedStats.p99,
    timestamps_ms: mergedLatencies,
  })

  const directTotal = results
    .filter((r) => r.test_name.startsWith('direct'))
    .reduce((sum, r) => sum + r.avg_ms * r.total_requests, 0)

  const proxyTotal = results
    .filter((r) => r.test_name.startsWith('proxy'))
    .reduce((sum, r) => sum + r.avg_ms * r.total_requests, 0)

  const improvement = directTotal - proxyTotal
  const improvementPercent = directTotal > 0 ? (improvement / directTotal) * 100 : 0

  destroyRequestMerger()

  return {
    results,
    summary: {
      direct_total_ms: directTotal,
      proxy_total_ms: proxyTotal,
      improvement_ms: improvement,
      improvement_percent: improvementPercent,
    },
  }
}

export function formatBenchmarkReport(report: BenchmarkReport): string {
  let output = 'HTTP Proxy Performance Benchmark Report\n'
  output += '='.repeat(50) + '\n\n'

  for (const result of report.results) {
    output += `Test: ${result.test_name}\n`
    output += `  Endpoint: ${result.method} ${result.endpoint}\n`
    output += `  Requests: ${result.total_requests} (${result.successful} ok, ${result.failed} failed)\n`
    output += `  Min: ${result.min_ms.toFixed(2)}ms\n`
    output += `  Max: ${result.max_ms.toFixed(2)}ms\n`
    output += `  Avg: ${result.avg_ms.toFixed(2)}ms\n`
    output += `  P50: ${result.p50_ms.toFixed(2)}ms\n`
    output += `  P95: ${result.p95_ms.toFixed(2)}ms\n`
    output += `  P99: ${result.p99_ms.toFixed(2)}ms\n\n`
  }

  output += 'Summary\n'
  output += '-'.repeat(50) + '\n'
  output += `Direct HTTP Total: ${report.summary.direct_total_ms.toFixed(2)}ms\n`
  output += `Proxy Total: ${report.summary.proxy_total_ms.toFixed(2)}ms\n`
  output += `Improvement: ${report.summary.improvement_ms.toFixed(2)}ms (${report.summary.improvement_percent.toFixed(2)}%)\n`

  return output
}
