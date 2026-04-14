'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { applications } from '@/lib/api';

type Application = {
  id: string;
  job_id: string | null;
  job_title: string;
  company: string;
  status: string;
  created_at: string;
  submitted_at: string | null;
  error_log: string | null;
};

const STATUS_STYLES: Record<string, string> = {
  submitted: 'text-green-400 bg-green-400/10',
  failed: 'text-red-400 bg-red-400/10',
  pending: 'text-yellow-400 bg-yellow-400/10',
  in_progress: 'text-yellow-400 bg-yellow-400/10',
  skipped: 'text-[rgba(245,242,236,0.3)] bg-[rgba(245,242,236,0.05)]',
};

const STATUS_FILTERS = ['all', 'submitted', 'pending', 'failed', 'skipped'];

export default function ApplicationsPage() {
  const router = useRouter();
  const { user, token, logout, isLoading } = useAuth();
  const [apps, setApps] = useState<Application[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  const perPage = 20;

  useEffect(() => {
    if (!isLoading && !token) router.push('/auth/login');
  }, [isLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    fetchApps();
  }, [token, page, statusFilter]);

  const fetchApps = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: perPage };
      if (statusFilter !== 'all') params.status_filter = statusFilter;
      const data = await applications.list(token, params);
      setApps(data.applications);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async (appId: string) => {
    if (!token) return;
    setRetrying(appId);
    try {
      await fetch(`http://localhost:8000/applications/${appId}/retry`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchApps();
    } catch (e) {
      console.error(e);
    } finally {
      setRetrying(null);
    }
  };

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  const totalPages = Math.ceil(total / perPage);

  if (isLoading || !user) {
    return (
      <div className="min-h-screen bg-[var(--night)] flex items-center justify-center">
        <div className="text-[var(--star)] animate-pulse font-serif text-2xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--paper)]">
      {/* Header */}
      <header className="bg-[var(--night)] border-b border-[rgba(245,242,236,0.06)]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="font-serif text-xl text-[#f5f2ec] italic">NightShift</Link>
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Dashboard</Link>
            <Link href="/jobs" className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Browse Jobs</Link>
            <Link href="/applications" className="text-xs text-[rgba(245,242,236,0.9)]">Applications</Link>
            <Link href="/intake" className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Settings</Link>
            <button onClick={handleLogout} className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Logout</button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Title row */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-serif text-4xl text-[var(--ink)] mb-1">Applications</h1>
            <p className="text-[var(--muted)] text-sm">{total} total</p>
          </div>
          <Link href="/jobs" className="btn-primary text-sm py-2.5 px-6">
            Browse Jobs →
          </Link>
        </div>

        {/* Filters */}
        <div className="flex gap-2 mb-6">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => { setStatusFilter(f); setPage(1); }}
              className={`px-4 py-1.5 text-xs capitalize transition-all ${
                statusFilter === f
                  ? 'bg-[var(--ink)] text-[var(--paper)]'
                  : 'border border-[var(--border)] text-[var(--muted)] hover:border-[var(--ink)]'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="bg-[var(--card)] border border-[var(--border)]">
          {loading ? (
            <div className="p-12 text-center text-[var(--muted)]">Loading...</div>
          ) : apps.length === 0 ? (
            <div className="p-16 text-center">
              <p className="font-serif text-2xl text-[var(--ink)] mb-3">No applications yet</p>
              <p className="text-sm text-[var(--muted)] mb-6">
                {statusFilter !== 'all'
                  ? `No ${statusFilter} applications found.`
                  : 'Browse jobs and apply to get started.'}
              </p>
              <Link href="/jobs" className="btn-primary text-sm py-2.5 px-6">Browse Jobs</Link>
            </div>
          ) : (
            <>
              {/* Header row */}
              <div className="grid grid-cols-[1fr_1fr_120px_160px_80px] gap-4 px-6 py-3 border-b border-[var(--border)] bg-[var(--paper)]">
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Job</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Company</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Status</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Date</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]"></span>
              </div>

              {apps.map((app) => (
                <div
                  key={app.id}
                  className="grid grid-cols-[1fr_1fr_120px_160px_80px] gap-4 px-6 py-4 border-b border-[var(--border)] last:border-0 items-center hover:bg-[rgba(0,0,0,0.01)] transition-colors"
                >
                  <span className="font-medium text-[var(--ink)] text-sm truncate">{app.job_title}</span>
                  <span className="text-sm text-[var(--muted)] truncate">{app.company}</span>
                  <span>
                    <span className={`text-xs px-2 py-1 capitalize ${STATUS_STYLES[app.status] || STATUS_STYLES.skipped}`}>
                      {app.status === 'in_progress' ? 'running' : app.status}
                    </span>
                  </span>
                  <span className="text-xs text-[var(--muted)]">
                    {new Date(app.submitted_at || app.created_at).toLocaleDateString('en-US', {
                      month: 'short', day: 'numeric', year: 'numeric',
                    })}
                  </span>
                  <span>
                    {(app.status === 'failed' || app.status === 'skipped') && (
                      <button
                        onClick={() => handleRetry(app.id)}
                        disabled={retrying === app.id}
                        className="text-xs text-[var(--star)] hover:underline disabled:opacity-50"
                      >
                        {retrying === app.id ? '...' : 'Retry'}
                      </button>
                    )}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => p - 1)}
              disabled={page === 1}
              className="px-4 py-2 text-sm border border-[var(--border)] text-[var(--muted)] hover:border-[var(--ink)] disabled:opacity-30 transition-all"
            >
              ← Prev
            </button>
            <span className="text-sm text-[var(--muted)] px-4">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page === totalPages}
              className="px-4 py-2 text-sm border border-[var(--border)] text-[var(--muted)] hover:border-[var(--ink)] disabled:opacity-30 transition-all"
            >
              Next →
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
