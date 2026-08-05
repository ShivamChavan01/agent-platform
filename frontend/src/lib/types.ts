export interface User {
  id: string;
  email: string;
  name: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  model: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  title: string | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  created_at: string;
  tool_call_id?: string | null;
  tool_name?: string | null;
  tool_arguments?: string | null;
  reasoning?: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ProjectFile {
  id: string;
  project_id: string;
  original_filename: string;
  storage_path: string;
  mime_type: string | null;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
}

export interface Preferences {
  default_model?: string | null;
  context_window?: number | null;
}

export interface UsageWindow {
  used_tokens: number;
  requests: number;
  cap_tokens: number;
  percent: number;
  seconds_until_reset: number;
}

export interface Usage {
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  window_hours: number;
  session: UsageWindow;
  weekly: UsageWindow;
}

export interface ModelOption {
  id: string;
  label: string;
  description: string;
}
