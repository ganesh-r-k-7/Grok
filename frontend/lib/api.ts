import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CSRF_COOKIE_NAME = "grokcsrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

let isRefreshing = false;
let refreshPromise: Promise<void> | null = null;

function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(new RegExp(`(^| )${CSRF_COOKIE_NAME}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : undefined;
}

async function refreshAccessToken(): Promise<void> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: {
          [CSRF_HEADER_NAME]: getCsrfToken() || "",
        },
      });

      if (!response.ok) {
        throw new Error("Token refresh failed");
      }
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  retryCount = 0
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  // Add CSRF token for unsafe methods
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers[CSRF_HEADER_NAME] = csrfToken;
    }
  }

  const response = await fetch(`${API_BASE}/api/v1${endpoint}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  // Handle 401 - try to refresh token once
  if (response.status === 401 && retryCount === 0 && endpoint !== "/auth/refresh" && endpoint !== "/auth/login" && endpoint !== "/auth/register") {
    try {
      await refreshAccessToken();
      // Retry the original request
      return apiRequest<T>(endpoint, options, retryCount + 1);
    } catch {
      // Refresh failed, throw the original error
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  get: <T>(endpoint: string) => apiRequest<T>(endpoint, { method: "GET" }),
  post: <T>(endpoint: string, data: unknown) =>
    apiRequest<T>(endpoint, { method: "POST", body: JSON.stringify(data) }),
  patch: <T>(endpoint: string, data: unknown) =>
    apiRequest<T>(endpoint, { method: "PATCH", body: JSON.stringify(data) }),
  delete: <T>(endpoint: string) => apiRequest<T>(endpoint, { method: "DELETE" }),
};

// Task types
export type TaskStatus = "todo" | "in_progress" | "completed";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TaskCreate {
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_at?: string | null;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_at?: string | null;
}

// Task API functions
export const tasksApi = {
  list: (params?: {
    page?: number;
    page_size?: number;
    status?: TaskStatus;
    priority?: TaskPriority;
    overdue?: boolean;
    due_before?: string;
    due_after?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return api.get<TaskListResponse>(`/tasks${query ? `?${query}` : ""}`);
  },

  get: (id: string) => api.get<Task>(`/tasks/${id}`),

  create: (data: TaskCreate) => api.post<Task>("/tasks", data),

  update: (id: string, data: TaskUpdate) => api.patch<Task>(`/tasks/${id}`, data),

  delete: (id: string) => api.delete<void>(`/tasks/${id}`),
};

// AI types
export type ConversationRole = "user" | "assistant" | "system" | "tool";

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ConversationCreate {
  title: string;
}

export interface ConversationUpdate {
  title: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: ConversationRole;
  content: string;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: ConversationRole;
  content: string;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: MessageResponse;
}

async function apiRequestStream(
  endpoint: string,
  data: unknown,
  retryCount = 0
): Promise<Response> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (csrfToken) {
    headers[CSRF_HEADER_NAME] = csrfToken;
  }

  const response = await fetch(`${API_BASE}/api/v1${endpoint}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(data),
  });

  if (response.status === 401 && retryCount === 0 && endpoint !== "/auth/refresh") {
    try {
      await refreshAccessToken();
      return apiRequestStream(endpoint, data, retryCount + 1);
    } catch {
      return response;
    }
  }

  return response;
}

// Streaming types
export interface StreamChunk {
  type: "content" | "tool_call" | "tool_result" | "done" | "error";
  content?: string;
  tool_call?: {
    id: string;
    type: "function";
    function: {
      name: string;
      arguments: string;
    };
  };
  tool_result?: {
    success: boolean;
    task?: any;
    tasks?: any[];
    total?: number;
    message?: string;
    error?: string;
  };
  error?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
  };
  conversation_id?: string;
}

// Auth/Integrations types
export interface IntegrationStatus {
  provider: string;
  connected: boolean;
  email?: string;
  name?: string;
  last_synced_at?: string;
}

export interface GoogleConnectResponse {
  authorization_url: string;
}

// Auth/Integrations API functions
export const authApi = {
  connectGoogle: () => api.post<GoogleConnectResponse>("/auth/google/connect", {}),
  getGoogleStatus: () => api.get<IntegrationStatus>("/auth/google/status"),
  disconnectGoogle: () => api.delete<void>("/auth/google/disconnect"),
};

// AI API functions
export const aiApi = {
  chat: (data: ChatRequest) => api.post<ChatResponse>("/ai/chat", data),

  chatStream: (data: ChatRequest) => {
    return apiRequestStream("/ai/chat/stream", data);
  },

  listConversations: (params?: { page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return api.get<{ conversations: Conversation[]; total: number; page: number; page_size: number; total_pages: number }>(
      `/ai/conversations${query ? `?${query}` : ""}`
    );
  },

  createConversation: (data: ConversationCreate) => api.post<Conversation>("/ai/conversations", data),

  getConversation: (id: string) => api.get<Conversation>(`/ai/conversations/${id}`),

  updateConversation: (id: string, data: ConversationUpdate) => api.patch<Conversation>(`/ai/conversations/${id}`, data),

  deleteConversation: (id: string) => api.delete<void>(`/ai/conversations/${id}`),

  getMessages: (conversationId: string, limit?: number) => {
    const searchParams = new URLSearchParams();
    if (limit) {
      searchParams.set("limit", String(limit));
    }
    const query = searchParams.toString();
    return api.get<{ messages: Message[] }>(`/ai/conversations/${conversationId}/messages${query ? `?${query}` : ""}`);
  },
};