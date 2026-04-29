export interface AppSettings {
  python_backend_url: string
  ollama_url: string
  default_model: string
  theme: string
  auto_save: boolean
  language: string
}

export interface ProjectMeta {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  status: string
  model_path: string
  nc_program_path: string
}
