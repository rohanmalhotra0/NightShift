/**
 * API client for NightShift backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: Record<string, unknown>;
  token?: string;
};

type ApiErrorDetail = { code?: string; message?: string; upgrade_url?: string } | string | null;

class ApiError extends Error {
  status: number;
  detail: ApiErrorDetail;

  constructor(message: string, status: number, detail: ApiErrorDetail = null) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = 'ApiError';
  }

  /** True for 402 Payment Required with an `upgrade_url` from the backend. */
  get isPaywall(): boolean {
    return (
      this.status === 402 &&
      typeof this.detail === 'object' &&
      this.detail !== null &&
      'upgrade_url' in this.detail
    );
  }

  /** Resolve `upgrade_url` from the detail object, falling back to /pricing. */
  get upgradeUrl(): string {
    if (
      typeof this.detail === 'object' &&
      this.detail !== null &&
      typeof this.detail.upgrade_url === 'string' &&
      this.detail.upgrade_url
    ) {
      return this.detail.upgrade_url;
    }
    return '/pricing';
  }
}

/**
 * Global handler invoked when any API call returns 402 with an
 * `upgrade_url`. Set by `AuthProvider` on mount so paywall errors
 * from anywhere in the app bounce the user to /pricing without each
 * page needing its own try/catch. Returns true if it took the
 * navigation, in which case the original request promise still
 * rejects so consumers can short-circuit.
 */
type PaywallHandler = (error: ApiError) => boolean;
let paywallHandler: PaywallHandler | null = null;

export function setPaywallHandler(handler: PaywallHandler | null): void {
  paywallHandler = handler;
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
    const detail: ApiErrorDetail = error?.detail ?? null;
    let message: string;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object' && 'message' in detail && detail.message) {
      message = detail.message as string;
    } else {
      message = 'Request failed';
    }
    const apiError = new ApiError(message, response.status, detail);
    if (apiError.isPaywall && paywallHandler) {
      // Fire-and-forget: handler decides whether to navigate. The error
      // is still thrown so awaiting code can stop.
      try {
        paywallHandler(apiError);
      } catch {
        /* never let a handler crash break the request flow */
      }
    }
    throw apiError;
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
    request<{
      id: string;
      email: string;
      tier: string;
      is_admin: boolean;
      subscription_status: string | null;
      current_period_end: string | null;
    }>('/auth/me', { token }),
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
    request<{ id: string; filename: string; is_primary: boolean }[]>('/users/resumes', { token }),

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
        id: string;
        title: string;
        company: string;
        location: string | null;
        url: string;
        source: string;
        salary_range: string | null;
        is_easy_apply: boolean;
        has_applied: boolean;
        scraped_at: string;
      }>;
      total: number;
      page: number;
      per_page: number;
    }>(`/jobs${query}`, { token });
  },

  get: (token: string, jobId: string) =>
    request<{
      id: string;
      title: string;
      company: string;
      location: string | null;
      description: string | null;
      url: string;
      salary_range: string | null;
      is_easy_apply: boolean;
      has_applied: boolean;
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
        id: string;
        job_id: string | null;
        job_title: string;
        company: string;
        status: string;
        created_at: string;
        submitted_at: string | null;
        error_log: string | null;
      }>;
      total: number;
      page: number;
      per_page: number;
    }>(`/applications${query}`, { token });
  },

  today: (token: string) =>
    request<{
      submitted: number;
      failed: number;
      pending: number;
      in_progress: number;
      total: number;
      daily_limit: number;
      remaining: number;
    }>('/applications/today', { token }),

  stats: (token: string, days?: number) =>
    request<{
      total_applications: number;
      successful_applications: number;
      failed_applications: number;
      success_rate: number;
      total_cost: number;
      avg_duration_seconds: number;
    }>(`/applications/stats${days ? `?days=${days}` : ''}`, { token }),

  apply: (token: string, jobIds: string[]) =>
    request<{ queued: number; skipped: number }>('/applications/apply', {
      method: 'POST',
      body: { job_ids: jobIds },
      token,
    }),

  retry: (token: string, applicationId: string) =>
    request<{ message: string }>(`/applications/${applicationId}/retry`, {
      method: 'POST',
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
    request<{ checkout_url: string; session_id: string }>('/payments/checkout', {
      method: 'POST',
      body: { tier, success_url: successUrl, cancel_url: cancelUrl },
      token,
    }),

  subscription: (token: string) =>
    request<{
      tier: string;
      status: string | null;
      current_period_end: string | null;
      cancel_at_period_end: boolean;
    }>('/payments/subscription', { token }),

  cancel: (token: string) =>
    request<{ message: string; cancel_at_period_end: boolean }>(
      '/payments/cancel',
      { method: 'POST', token }
    ),

  resume: (token: string) =>
    request<{ message: string; cancel_at_period_end: boolean }>(
      '/payments/resume',
      { method: 'POST', token }
    ),

  portal: (token: string, returnUrl: string) =>
    request<{ url: string }>('/payments/portal', {
      method: 'POST',
      body: { return_url: returnUrl },
      token,
    }),
};

export { ApiError };
