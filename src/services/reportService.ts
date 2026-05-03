import axios from 'axios'
import { DEFAULT_URLS } from '@/constants'

export interface ReACTStep {
  step_number: number
  step_type: 'thought' | 'action' | 'observation' | 'final_answer'
  content: string
  tool_name: string | null
  tool_input: Record<string, unknown> | null
  tool_output: Record<string, unknown> | null
  duration_ms: number | null
}

export interface Report {
  report: string
  reasoning_steps: ReACTStep[]
  total_steps: number
}

export interface ReportMetadata {
  task_id: string
  generated_at: string
  model: string
  total_duration_ms: number
  total_tokens: number
}

class ReportService {
  private baseUrl: string

  constructor(baseUrl: string = DEFAULT_URLS.PYTHON_BACKEND) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  async generateReport(processTaskId?: string): Promise<{ task_id: string; status: string; message: string }> {
    const response = await axios.post(`${this.baseUrl}/api/v1/reports/generate`, {
      process_task_id: processTaskId || null
    })
    return response.data
  }

  async getReport(taskId: string): Promise<Report> {
    const response = await axios.get(`${this.baseUrl}/api/v1/reports/${taskId}`)
    return response.data.data
  }

  async getReasoningSteps(taskId: string): Promise<ReACTStep[]> {
    const response = await axios.get(`${this.baseUrl}/api/v1/reports/${taskId}/reasoning`)
    return response.data.data.reasoning_steps
  }
}

export const reportService = new ReportService()
