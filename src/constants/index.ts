export const API_ENDPOINTS = {
  WORKFLOW: {
    PROCESS_PLAN: '/api/workflow/process-plan',
    PROCESS_PLAN_ASYNC: '/api/workflow/process-plan-async',
  },
  CAD: {
    THREE_VIEW_TO_3D: '/api/cad/three-view-to-3d',
    CADQUERY: '/api/cad/cadquery',
    TASK_STATUS: (taskId: string) => `/api/cad/tasks/${taskId}`,
    MODEL_DOWNLOAD: (taskId: string) => `/api/cad/models/${taskId}/download`,
  },
  TASKS: {
    LIST: '/api/v1/tasks',
    CREATE: '/api/v1/tasks',
    GET: (taskId: string) => `/api/v1/tasks/${taskId}`,
    DELETE: (taskId: string) => `/api/v1/tasks/${taskId}`,
    STREAM: (taskId: string) => `/api/v1/tasks/${taskId}/stream`,
  },
} as const

export const DEFAULT_SETTINGS = {
  PYTHON_BACKEND_URL: 'http://localhost:8765',
  OLLAMA_URL: 'http://localhost:11434',
  DEFAULT_MODEL: 'qwen2.5-coder:7b',
  THEME: 'light',
  AUTO_SAVE: true,
  LANGUAGE: 'zh-CN',
  CLOUD_BASE_URL: 'https://api.openai.com/v1',
  CLOUD_MODEL: 'gpt-3.5-turbo',
} as const

export const DEFAULT_URLS = {
  PYTHON_BACKEND: DEFAULT_SETTINGS.PYTHON_BACKEND_URL,
  OLLAMA: DEFAULT_SETTINGS.OLLAMA_URL,
} as const

export const POLLING_CONFIG = {
  INTERVAL_MS: 2000,
  TIMEOUT_MS: 300000,
} as const

export const MODEL_CONSTANTS = {
  RECOMMENDED_MODELS: [
    { name: 'qwen2.5-coder:7b', size: '4.7 GB', category: '代码' },
    { name: 'deepseek-r1:7b', size: '4.1 GB', category: '推理' },
    { name: 'llama3.2:3b', size: '2.0 GB', category: '通用' },
  ],
} as const

export const FILE_CONSTANTS = {
  MAX_FILE_SIZE: 10 * 1024 * 1024,
  ACCEPTED_IMAGE_TYPES: ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'],
} as const

export const STORAGE_KEYS = {
  APP_SETTINGS: 'lingjing-settings',
  PROJECTS: 'lingjing-projects',
  THEME: 'lingjing-theme',
  LANGUAGE: 'lingjing-language',
} as const

export const THREE_VIEWER_CONFIG = {
  SCENE_BACKGROUND_COLOR: 0xf0f0f0,
  CAMERA_FOV: 75,
  CAMERA_NEAR: 0.1,
  CAMERA_FAR: 10000,
  CAMERA_POSITION: { x: 100, y: 100, z: 100 },
  CAMERA_DISTANCE_FACTOR: 1.5,
  DAMPING_FACTOR: 0.05,
  MAX_PIXEL_RATIO: 2,
  GRID_SIZE: 200,
  GRID_DIVISIONS: 20,
  MODEL_COLOR: 0x409EFF,
  MODEL_SPECULAR: 0x111111,
  MODEL_SHININESS: 200,
  SUPPORTED_FORMATS: ['stl', 'obj', 'gltf', 'glb'] as const,
} as const
