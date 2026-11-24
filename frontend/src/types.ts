export interface QuickAction {
  id: string
  label: string
  prompt: string
  icon: string
}

export interface Settings {
  identity: {
    name: string
    user_name: string
    tagline: string
    greeting: string
    tone: 'warm_concise' | 'professional' | 'playful' | 'direct'
    system_prompt: string
  }
  appearance: {
    theme: 'midnight' | 'aurora' | 'obsidian' | 'forest' | 'light'
    accent_color: string
    secondary_color: string
    orb_style: 'aurora' | 'pulse' | 'rings' | 'minimal'
    density: 'comfortable' | 'compact'
    glass_effects: boolean
    font_scale: number
  }
  ai: {
    provider: 'ollama' | 'gemini' | 'openai_compat'
    ollama_base_url: string
    ollama_model: string
    gemini_api_key: string
    gemini_model: string
    openai_base_url: string
    openai_api_key: string
    openai_model: string
    temperature: number
    max_tool_steps: number
  }
  voice: {
    enabled: boolean
    auto_speak: boolean
    tts_engine: 'edge' | 'browser' | 'windows_sapi'
    edge_voice: string
    rate: string
    pitch: string
    stt_language: string
  }
  capabilities: {
    tasks_notes_reminders: boolean
    knowledge_base: boolean
    web_search: boolean
    daily_briefing: boolean
    system_automation: boolean
    google_workspace: boolean
  }
  automation: {
    allow_app_launch: boolean
    require_approval_for_shell: boolean
    allowed_apps: Record<string, string>
  }
  briefing: {
    location: string
    topics: string[]
    morning_time: string
    include_weather: boolean
    include_news: boolean
    include_tasks: boolean
    include_google: boolean
  }
  knowledge_base: {
    folders: string[]
    extensions: string[]
    chunk_size: number
    chunk_overlap: number
  }
  quick_actions: QuickAction[]
  google: {
    enabled: boolean
    calendar_enabled: boolean
    gmail_enabled: boolean
    credentials_file: string
    token_file: string
  }
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ToolEvent {
  tool: string
  arguments: Record<string, unknown>
  result: Record<string, unknown>
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  tool_events: ToolEvent[]
  provider?: string
  model?: string
  created_at: string
}

export interface TaskItem {
  id: string
  title: string
  notes: string
  status: 'open' | 'done'
  priority: 'low' | 'medium' | 'high'
  due_date: string
  tags: string[]
  created_at: string
}

export interface NoteItem {
  id: string
  title: string
  content: string
  tags: string[]
  pinned: boolean
  created_at: string
  updated_at: string
}

export interface ReminderItem {
  id: string
  title: string
  remind_at: string
  repeat: 'none' | 'daily' | 'weekly'
  triggered: boolean
  created_at: string
}

export interface PendingApproval {
  id: string
  tool_name: string
  arguments: Record<string, unknown>
  summary: string
  tier: number
  created_at: string
  status: string
}

export interface AuditItem {
  id: string
  timestamp: string
  tool_name: string
  tier: number
  summary: string
  details: Record<string, unknown>
  status: string
}

export interface GoogleStatus {
  credentials_found: boolean
  credentials_path: string
  token_found: boolean
  connected: boolean
  email: string
  scopes: string[]
}

export interface SystemInfo {
  ok: boolean
  os: string
  cpu_percent?: number
  memory_total_gb?: number
  memory_used_gb?: number
  memory_percent?: number
  disk_total_gb: number
  disk_used_gb: number
  disk_percent: number
  battery_percent?: number | null
  battery_charging?: boolean | null
  computer_name?: string
  user_name?: string
}
