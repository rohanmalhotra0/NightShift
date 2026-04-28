'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { jobs, applications, ApiError } from '@/lib/api';

type Job = {
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
};

export default function JobsPage() {
  const router = useRouter();
  const { user, token, logout, isLoading } = useAuth();
  const [jobList, setJobList] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [easyApplyOnly, setEasyApplyOnly] = useState(false);
  const [hideApplied, setHideApplied] = useState(true);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<string | null>(null);

  const perPage = 20;

  useEffect(() => {
    if (!isLoading && !token) router.push('/auth/login');
  }, [isLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    fetchJobs();
  }, [token, page, search, easyApplyOnly, hideApplied]);

  const fetchJobs = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        per_page: perPage,
        hide_applied: hideApplied,
      };
      if (search) params.search = search;
      if (easyApplyOnly) params.easy_apply_only = true;

      const data = await jobs.list(token, params);
      setJobList(data.jobs);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const unapplied = jobList.filter((j) => !j.has_applied).map((j) => j.id);
    setSelected(new Set(unapplied));
  };

  const handleApply = async () => {
    if (!token || selected.size === 0) return;
    setApplying(true);
    setApplyResult(null);
    try {
      const result = await applications.apply(token, Array.from(selected));
      setApplyResult(`Queued ${result.queued} application${result.queued !== 1 ? 's' : ''}. The bot will apply tonight.`);
      setSelected(new Set());
      await fetchJobs();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.isPaywall) {
        router.push('/pricing');
        return;
      }
      const message = e instanceof Error ? e.message : 'Failed to queue applications';
      setApplyResult(message);
    } finally {
      setApplying(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
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
            <Link href="/jobs" className="text-xs text-[rgba(245,242,236,0.9)]">Browse Jobs</Link>
            <Link href="/applications" className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Applications</Link>
            <Link href="/intake" className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Settings</Link>
            <button onClick={handleLogout} className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors">Logout</button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Title */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="font-serif text-4xl text-[var(--ink)] mb-1">Browse Jobs</h1>
            <p className="text-[var(--muted)] text-sm">
              {total} matching job{total !== 1 ? 's' : ''} · select any to apply
            </p>
          </div>

          {/* Apply button */}
          {selected.size > 0 && (
            <div className="flex flex-col items-end gap-2">
              <button
                onClick={handleApply}
                disabled={applying}
                className="btn-primary disabled:opacity-50"
              >
                {applying ? 'Queueing...' : `Apply to ${selected.size} job${selected.size !== 1 ? 's' : ''} →`}
              </button>
              <button onClick={() => setSelected(new Set())} className="text-xs text-[var(--muted)] hover:text-[var(--ink)]">
                Clear selection
              </button>
            </div>
          )}
        </div>

        {/* Apply result banner */}
        {applyResult && (
          <div className={`mb-6 px-5 py-4 text-sm border ${
            applyResult.startsWith('Queued')
              ? 'bg-green-50 border-green-200 text-green-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}>
            {applyResult}
            <button onClick={() => setApplyResult(null)} className="ml-4 underline text-xs">Dismiss</button>
          </div>
        )}

        {/* Search & filters */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-64">
            <input
              type="text"
              placeholder="Search job title or company..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="flex-1 border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm text-[var(--ink)] placeholder-[var(--muted)] focus:border-[var(--ink)] focus:outline-none transition-colors"
            />
            <button type="submit" className="px-4 py-2 bg-[var(--ink)] text-[var(--paper)] text-sm hover:opacity-80 transition-opacity">
              Search
            </button>
            {search && (
              <button type="button" onClick={() => { setSearch(''); setSearchInput(''); setPage(1); }} className="px-3 py-2 text-sm border border-[var(--border)] text-[var(--muted)] hover:border-[var(--ink)]">
                ✕
              </button>
            )}
          </form>

          <label className="flex items-center gap-2 cursor-pointer text-sm text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
            <input
              type="checkbox"
              checked={easyApplyOnly}
              onChange={(e) => { setEasyApplyOnly(e.target.checked); setPage(1); }}
              className="w-4 h-4"
            />
            Easy Apply only
          </label>

          <label className="flex items-center gap-2 cursor-pointer text-sm text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
            <input
              type="checkbox"
              checked={hideApplied}
              onChange={(e) => { setHideApplied(e.target.checked); setPage(1); }}
              className="w-4 h-4"
            />
            Hide applied
          </label>

          {jobList.length > 0 && (
            <button onClick={selectAll} className="text-sm text-[var(--star)] hover:underline ml-auto">
              Select all on page
            </button>
          )}
        </div>

        {/* Jobs list */}
        <div className="bg-[var(--card)] border border-[var(--border)]">
          {loading ? (
            <div className="p-12 text-center text-[var(--muted)]">Loading jobs...</div>
          ) : jobList.length === 0 ? (
            <div className="p-16 text-center">
              <p className="font-serif text-2xl text-[var(--ink)] mb-3">No jobs found</p>
              <p className="text-sm text-[var(--muted)] mb-2">
                {search
                  ? `No jobs matching "${search}".`
                  : 'No jobs have been scraped yet.'}
              </p>
              <p className="text-xs text-[var(--muted)]">
                Jobs are scraped nightly based on your preferences in{' '}
                <Link href="/intake" className="text-[var(--star)] hover:underline">Settings</Link>.
              </p>
            </div>
          ) : (
            <>
              {/* Column headers */}
              <div className="grid grid-cols-[40px_1fr_1fr_120px_100px_80px] gap-4 px-6 py-3 border-b border-[var(--border)] bg-[var(--paper)]">
                <span />
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Job</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Company / Location</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Salary</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Source</span>
                <span className="text-[10px] tracking-widest uppercase text-[var(--muted)]">Status</span>
              </div>

              {jobList.map((job) => (
                <div
                  key={job.id}
                  className={`grid grid-cols-[40px_1fr_1fr_120px_100px_80px] gap-4 px-6 py-4 border-b border-[var(--border)] last:border-0 items-center transition-colors cursor-pointer ${
                    selected.has(job.id) ? 'bg-[rgba(200,185,122,0.08)]' : 'hover:bg-[rgba(0,0,0,0.01)]'
                  } ${job.has_applied ? 'opacity-50' : ''}`}
                  onClick={() => !job.has_applied && toggleSelect(job.id)}
                >
                  {/* Checkbox */}
                  <div className={`w-5 h-5 border flex items-center justify-center transition-colors ${
                    job.has_applied
                      ? 'border-[var(--border)] bg-[var(--border)] cursor-not-allowed'
                      : selected.has(job.id)
                      ? 'bg-[var(--star)] border-[var(--star)]'
                      : 'border-[var(--border)] hover:border-[var(--star)]'
                  }`}>
                    {(selected.has(job.id) || job.has_applied) && (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke={job.has_applied ? '#999' : 'var(--night)'} strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>

                  {/* Title */}
                  <div>
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="font-medium text-[var(--ink)] text-sm hover:text-[var(--star)] transition-colors"
                    >
                      {job.title}
                    </a>
                    {job.is_easy_apply && (
                      <span className="ml-2 text-[10px] tracking-widest uppercase text-[var(--star)]">Easy Apply</span>
                    )}
                  </div>

                  {/* Company / Location */}
                  <div>
                    <p className="text-sm text-[var(--ink)]">{job.company}</p>
                    {job.location && <p className="text-xs text-[var(--muted)]">{job.location}</p>}
                  </div>

                  {/* Salary */}
                  <span className="text-xs text-[var(--muted)]">{job.salary_range || '—'}</span>

                  {/* Source */}
                  <span className="text-xs text-[var(--muted)] capitalize">{job.source}</span>

                  {/* Status */}
                  <span className="text-xs">
                    {job.has_applied ? (
                      <span className="text-green-600">Applied</span>
                    ) : selected.has(job.id) ? (
                      <span className="text-[var(--star)]">Selected</span>
                    ) : (
                      <span className="text-[var(--muted)]">—</span>
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
            <span className="text-sm text-[var(--muted)] px-4">{page} / {totalPages}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page === totalPages}
              className="px-4 py-2 text-sm border border-[var(--border)] text-[var(--muted)] hover:border-[var(--ink)] disabled:opacity-30 transition-all"
            >
              Next →
            </button>
          </div>
        )}

        {/* Help text */}
        <p className="text-center text-xs text-[var(--muted)] mt-8">
          Select jobs above and click <strong>Apply</strong> to queue them. The bot will apply automatically — you'll see results in{' '}
          <Link href="/applications" className="text-[var(--star)] hover:underline">Applications</Link>.
        </p>
      </main>
    </div>
  );
}
