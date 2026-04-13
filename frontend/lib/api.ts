/**
 * API client for NightShift backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: Record<string, unknown>;
  token?: string;
};

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new ApiError(error.detail || 'Request failed', response.status);
  }

  return response.json();
}

// Auth
export const auth = {
  signup: (email: string, password: string) =>
    request<{ access_token: string; expires_in: number }>('/auth/signup', {
      method: 'POST',
      body: { email, password },
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string; expires_in: number }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    }),

  getMe: (token: string) =>
    request<{ id: number; email: string; tier: string }>('/auth/me', { token }),
};

// Users
export const users = {
  getPrefs: (token: string) =>
    request<{
      job_titles: string[];
      locations: string[];
      salary_min: number | null;
      work_auth: string | null;
      remote_pref: string;
      generate_cover_letter: boolean;
      sheets_id: string | null;
    }>('/users/prefs', { token }),

  updatePrefs: (token: string, prefs: Record<string, unknown>) =>
    request('/users/prefs', { method: 'PUT', body: prefs, token }),

  getResumes: (token: string) =>
    request<{ id: number; filename: string; is_primary: boolean }[]>('/users/resumes', { token }),

  createSheet: (token: string) =>
    request<{ sheets_id: string; url: string }>('/users/sheets/create', { method: 'POST', token }),
};

// Jobs
export const jobs = {
  list: (token: string, params?: Record<string, string | number | boolean>) => {
    const query = params
      ? '?' + new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString()
      : '';
    return request<{
      jobs: Array<{
        id: number;
        title: string;
        company: string;
        location: string;
        url: string;
        source: string;
        is_easy_apply: boolean;
        has_applied: boolean;
      }>;
      total: number;
      page: number;
      per_page: number;
    }>(`/jobs${query}`, { token });
  },

  get: (token: string, jobId: number) =>
    request<{
      id: number;
      title: string;
      company: string;
      description: string;
      url: string;
    }>(`/jobs/${jobId}`, { token }),

  stats: (token: string) =>
    request<{
      total_matching_jobs: number;
      new_jobs_today: number;
      unapplied_matching: number;
    }>('/jobs/stats/summary', { token }),
};

// Applications
export const applications = {
  list: (token: string, params?: Record<string, string | number>) => {
    const query = params
      ? '?' + new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString()
      : '';
    return request<{
      applications: Array<{
        id: number;
        job_title: string;
        company: string;
        status: string;
        queued_at: string;
        submitted_at: string | null;
      }>;
      total: number;
    }>(`/applications${query}`, { token });
  },

  today: (token: string) =>
    request<{
      submitted: number;
      failed: number;
      pending: number;
      daily_limit: number;
      remaining: number;
    }>('/applications/today', { token }),

  stats: (token: string, days?: number) =>
    request<{
      total_applications: number;
      successful_applications: number;
      success_rate: number;
      total_cost: number;
    }>(`/applications/stats${days ? `?days=${days}` : ''}`, { token }),

  apply: (token: string, jobIds: number[]) =>
    request<{ queued: number }>('/applications/apply', {
      method: 'POST',
      body: { job_ids: jobIds },
      token,
    }),
};

// Payments
export const payments = {
  pricing: () =>
    request<{
      tiers: Array<{
        id: string;
        name: string;
        price: number;
        apps_per_night: number;
        features: string[];
      }>;
    }>('/payments/pricing'),

  checkout: (token: string, tier: string, successUrl: string, cancelUrl: string) =>
    request<{ checkout_url: string }>('/payments/checkout', {
      method: 'POST',
      body: { tier, success_url: successUrl, cancel_url: cancelUrl },
      token,
    }),

  subscription: (token: string) =>
    request<{ tier: string; status: string }>('/payments/subscription', { token }),
};

export { ApiError };
