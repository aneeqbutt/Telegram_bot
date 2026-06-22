const BASE = "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Articles
export const getArticles = (params?: { skip?: number; limit?: number; category?: string; is_posted?: boolean }) => {
  const q = new URLSearchParams();
  if (params?.skip !== undefined) q.set("skip", String(params.skip));
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  if (params?.category) q.set("category", params.category);
  if (params?.is_posted !== undefined) q.set("is_posted", String(params.is_posted));
  return request<Article[]>(`/articles?${q}`);
};
export const getArticle = (id: string) => request<Article>(`/articles/${id}`);

// Sources
export const getSources = () => request<Source[]>("/sources");
export const createSource = (data: Partial<Source>) => request<Source>("/sources", { method: "POST", body: JSON.stringify(data) });
export const updateSource = (id: string, data: Partial<Source>) => request<Source>(`/sources/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteSource = (id: string) => request(`/sources/${id}`, { method: "DELETE" });

// Categories
export const getCategories = () => request<Category[]>("/categories");
export const createCategory = (data: Partial<Category>) => request<Category>("/categories", { method: "POST", body: JSON.stringify(data) });
export const updateCategory = (id: string, data: Partial<Category>) => request<Category>(`/categories/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteCategory = (id: string) => request(`/categories/${id}`, { method: "DELETE" });

// Keywords
export const getKeywords = (category?: string) => {
  const q = category ? `?category=${category}` : "";
  return request<Keyword[]>(`/keywords${q}`);
};
export const createKeyword = (data: Partial<Keyword>) => request<Keyword>("/keywords", { method: "POST", body: JSON.stringify(data) });
export const deleteKeyword = (id: string) => request(`/keywords/${id}`, { method: "DELETE" });

// Channels
export const getChannels = () => request<Channel[]>("/channels");
export const createChannel = (data: Partial<Channel>) => request<Channel>("/channels", { method: "POST", body: JSON.stringify(data) });
export const updateChannel = (id: string, data: Partial<Channel>) => request<Channel>(`/channels/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteChannel = (id: string) => request(`/channels/${id}`, { method: "DELETE" });

// Types
export interface Article {
  _id: string;
  title: string;
  url: string;
  content: string;
  source_id: string;
  category: string;
  is_posted: boolean;
  published_at: string;
  scraped_at: string;
}

export interface Source {
  _id: string;
  name: string;
  base_url: string;
  is_active: boolean;
}

export interface Category {
  _id: string;
  name: string;
  description?: string;
  is_active: boolean;
}

export interface Keyword {
  _id: string;
  word: string;
  category_name: string;
  weight: number;
}

export interface Channel {
  _id: string;
  name: string;
  telegram_id: string;
  is_active: boolean;
  post_interval_minutes: number;
}
