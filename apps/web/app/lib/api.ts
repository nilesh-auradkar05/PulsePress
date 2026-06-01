// Minimal typed API client for PulsePress.
// Local passwordless dev-auth is enabled only when NEXT_PUBLIC_AUTH_MODE=local.

export const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "production";
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (AUTH_MODE === "local" ? "http://localhost:8000" : "");
export const DEV_TOKEN_KEY = "pulsepress_dev_token";

export type User = {
  id: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type Publication = {
  id: string;
  owner_user_id: string;
  handle: string;
  name: string;
  description: string | null;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type PublicationList = {
  items: Publication[];
  next_cursor: string | null;
};

export type PublicationCreate = {
  handle: string;
  name: string;
  description?: string | null;
};

export type PublicationUpdate = {
  name?: string;
  description?: string | null;
  avatar_url?: string | null;
};

export type PostStatus = "draft" | "published" | "archived";
export type PostVisibility = "free" | "paid";

export type Post = {
  id: string;
  publication_id: string;
  author_user_id: string;
  title: string;
  slug: string;
  status: PostStatus;
  visibility: PostVisibility;
  published_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PostRead = Post & {
  body: string | null;
  entitled: boolean;
};

export type PostList = {
  items: Post[];
  next_cursor: string | null;
};

export type PostCreate = {
  title: string;
  body: string;
  visibility: PostVisibility;
};

export type PostUpdate = Partial<PostCreate>;

export type PostPublishResult = {
  post_id: string;
  status: "published";
  published_at: string;
  version_id: string;
  newsletter_status: "queued" | "already_processed";
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function ensureApiBaseUrl(): string {
  if (!API_BASE_URL) {
    throw new ApiError(500, "PulsePress API base URL is not configured");
  }
  return API_BASE_URL;
}

function ensureLocalAuth(): void {
  if (AUTH_MODE !== "local") {
    throw new ApiError(501, "Local development auth is disabled in this environment");
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(DEV_TOKEN_KEY);
}

export function setToken(token: string): void {
  window.sessionStorage.setItem(DEV_TOKEN_KEY, token);
}

export function clearToken(): void {
  window.sessionStorage.removeItem(DEV_TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${ensureApiBaseUrl()}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail; // RFC 7807 Problem Details
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function withQuery(path: string, params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const suffix = search.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export const api = {
  register: (email: string, displayName: string) => {
    ensureLocalAuth();
    return request<TokenResponse>("/local/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, display_name: displayName }),
    });
  },
  login: (email: string) => {
    ensureLocalAuth();
    return request<TokenResponse>("/local/auth/login", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },
  me: () => request<User>("/v1/me"),
  listPublications: (params?: { owner?: "me" }) =>
    request<PublicationList>(withQuery("/v1/publications", { owner: params?.owner })),
  createPublication: (body: PublicationCreate) =>
    request<Publication>("/v1/publications", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updatePublication: (publicationId: string, body: PublicationUpdate) =>
    request<Publication>(`/v1/publications/${publicationId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listPosts: (publicationId: string, params?: { status?: PostStatus }) =>
    request<PostList>(
      withQuery(`/v1/publications/${publicationId}/posts`, { status: params?.status }),
    ),
  createPost: (publicationId: string, body: PostCreate) =>
    request<Post>(`/v1/publications/${publicationId}/posts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPost: (postId: string) => request<PostRead>(`/v1/posts/${postId}`),
  updatePost: (postId: string, body: PostUpdate) =>
    request<Post>(`/v1/posts/${postId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  publishPost: (postId: string) =>
    request<PostPublishResult>(`/v1/posts/${postId}/publish`, { method: "POST" }),
  archivePost: (postId: string) => request<Post>(`/v1/posts/${postId}`, { method: "DELETE" }),
};
