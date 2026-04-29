export interface ProcessPlanResult {
  extracted_params: {
    material?: string
    part_type?: string
    tolerance?: string
    surface_roughness?: string
  }
  process_route: Array<{
    step: number
    operation: string
    machine: string
    description: string
  }>
  cutting_parameters: {
    parameters: Array<{
      step: number
      operation: string
      v: string
      f: string
      ap: string
      n: string
    }>
  }
  nc_code: string
  verification_result: {
    summary?: string
    is_valid: boolean
    issues?: Array<{
      type: string
      description: string
      severity: 'high' | 'medium' | 'low'
    }>
  }
  repair_suggestions?: string
}
