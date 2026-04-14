'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { applications, jobs, users } from '@/lib/api';

type TodayStats = {
  submitted: number;
  failed: number;
  pending: number;
  daily_limit: number;
  remaining: number;
};

type JobStats = {
  total_matching_jobs: number;
  new_jobs_today: number;
  unapplied_matching: number;
};

type Application = {
  id: number;
  job_title: string;
  company: string;
  status: string;
  queued_at: string;
  submitted_at: string | null;
};

type UserStats = {
  total_applications: number;
  successful_applications: number;
  success_rate: number;
  total_cost: number;
};

export default function DashboardPage() {
  const router = useRouter();
  const { user, token, logout, isLoading } = useAuth();
  const [todayStats, setTodayStats] = useState<TodayStats | null>(null);
  const [jobStats, setJobStats] = useState<JobStats | null>(null);
  const [recentApps, setRecentApps] = useState<Application[]>([]);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [sheetsUrl, setSheetsUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !token) {
      router.push('/auth/login');
    }
  }, [isLoading, token, router]);

  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      try {
        const [today, jobData, appList, stats, prefs] = await Promise.all([
          applications.today(token),
          jobs.stats(token),
          applications.list(token, { per_page: 5 }),
          applications.stats(token, 30),
          users.getPrefs(token),
        ]);

        setTodayStats(today);
        setJobStats(jobData);
        setRecentApps(appList.applications);
        setUserStats(stats);
        if (prefs.sheets_id) {
          setSheetsUrl(`https://docs.google.com/spreadsheets/d/${prefs.sheets_id}`);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      }
    };

    fetchData();
  }, [token]);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  if (isLoading || !user) {
    return (
      <div className="min-h-screen bg-[var(--night)] flex items-center justify-center">
        <div className="text-[var(--star)] animate-pulse font-serif text-2xl">Loading...</div>
      </div>
    );
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'submitted':
        return 'text-green-400';
      case 'failed':
        return 'text-red-400';
      case 'pending':
      case 'in_progress':
        return 'text-yellow-400';
      default:
        return 'text-[rgba(245,242,236,0.4)]';
    }
  };

  const isAdmin = user.is_admin || user.tier === 'admin';

  return (
    <div className="min-h-screen bg-[var(--paper)]">
      {/* Header */}
      <header className="bg-[var(--night)] border-b border-[rgba(245,242,236,0.06)]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="font-serif text-xl text-[#f5f2ec] italic">
            NightShift
          </Link>
          <div className="flex items-center gap-6">
            <span className="text-sm text-[rgba(245,242,236,0.5)]">{user.email}</span>
            <span className={`px-3 py-1 text-[10px] font-medium tracking-widest uppercase ${
              isAdmin
                ? 'bg-[var(--star)] text-[var(--night)]'
                : 'bg-[rgba(245,242,236,0.1)] text-[rgba(245,242,236,0.6)]'
            }`}>
              {isAdmin ? 'Admin' : user.tier}
            </span>
            <Link
              href="/intake"
              className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors"
            >
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Welcome */}
        <div className="mb-10">
          <h1 className="font-serif text-4xl text-[var(--ink)] mb-2">Good evening</h1>
          <p className="text-[var(--muted)] text-sm">
            {isAdmin ? 'Admin mode active - unlimited applications' : `Your applications are running tonight at 10 PM`}
          </p>
        </div>

        {/* Stats grid */}
        <div className="grid md:grid-cols-4 gap-6 mb-10">
          <div className="bg-[var(--card)] border border-[var(--border)] p-6">
            <p className="text-[11px] tracking-widest uppercase text-[var(--muted)] mb-2">Today</p>
            <p className="font-serif text-4xl text-[var(--ink)]">
              {todayStats?.submitted || 0}
              <span className="text-lg text-[var(--muted)]">/{isAdmin ? '∞' : (todayStats?.daily_limit || 0)}</span>
            </p>
            <p className="text-xs text-[var(--muted)] mt-1">applications sent</p>
          </div>

          <div className="bg-[var(--card)] border border-[var(--border)] p-6">
            <p className="text-[11px] tracking-widest uppercase text-[var(--muted)] mb-2">Queue</p>
            <p className="font-serif text-4xl text-[var(--ink)]">
              {jobStats?.unapplied_matching || 0}
            </p>
            <p className="text-xs text-[var(--muted)] mt-1">matching jobs</p>
          </div>

          <div className="bg-[var(--card)] border border-[var(--border)] p-6">
            <p className="text-[11px] tracking-widest uppercase text-[var(--muted)] mb-2">Success</p>
            <p className="font-serif text-4xl text-[var(--ink)]">
              {userStats ? `${Math.round(userStats.success_rate * 100)}%` : '0%'}
            </p>
            <p className="text-xs text-[var(--muted)] mt-1">last 30 days</p>
          </div>

          <div className="bg-[var(--card)] border border-[var(--border)] p-6">
            <p className="text-[11px] tracking-widest uppercase text-[var(--muted)] mb-2">Total</p>
            <p className="font-serif text-4xl text-[var(--ink)]">
              {userStats?.total_applications || 0}
            </p>
            <p className="text-xs text-[var(--muted)] mt-1">applications ever</p>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Recent applications */}
          <div className="lg:col-span-2">
            <div className="bg-[var(--card)] border border-[var(--border)]">
              <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
                <h2 className="font-serif text-xl">Recent Applications</h2>
                <Link href="/applications" className="text-xs text-[var(--star)] hover:underline">
                  View all
                </Link>
              </div>

              {recentApps.length === 0 ? (
                <div className="p-12 text-center">
                  <p className="text-[var(--muted)] mb-2">No applications yet</p>
                  <p className="text-xs text-[var(--muted)]">
                    Applications will start running tonight at 10 PM
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-[var(--border)]">
                  {recentApps.map((app) => (
                    <div key={app.id} className="px-6 py-4 flex items-center justify-between">
                      <div>
                        <p className="font-medium text-[var(--ink)]">{app.job_title}</p>
                        <p className="text-sm text-[var(--muted)]">{app.company}</p>
                      </div>
                      <div className="text-right">
                        <p className={`text-sm capitalize ${statusColor(app.status)}`}>
                          {app.status === 'submitted' ? '✓ Submitted' : app.status}
                        </p>
                        <p className="text-xs text-[var(--muted)]">
                          {new Date(app.submitted_at || app.queued_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Side panel */}
          <div className="space-y-6">
            {/* Google Sheets */}
            <div className="bg-[var(--card)] border border-[var(--border)] p-6">
              <h3 className="font-serif text-lg mb-4">Application Log</h3>
              {sheetsUrl ? (
                <a
                  href={sheetsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 bg-[rgba(200,185,122,0.1)] border border-[rgba(200,185,122,0.2)] text-[var(--star)] hover:bg-[rgba(200,185,122,0.15)] transition-colors"
                >
                  <span className="text-sm">Open Google Sheets</span>
                  <span></span>
                </a>
              ) : (
                <div className="text-center py-4">
                  <p className="text-sm text-[var(--muted)] mb-4">
                    Track all applications in Google Sheets
                  </p>
                  <button className="btn-primary text-sm py-2 px-4">
                    Create Sheet
                  </button>
                </div>
              )}
            </div>

            {/* 30-Day Summary */}
            <div className="bg-[var(--card)] border border-[var(--border)] p-6">
              <h3 className="font-serif text-lg mb-4">30-Day Summary</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--muted)]">Total Applications</span>
                  <span className="font-medium">{userStats?.total_applications || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--muted)]">Successful</span>
                  <span className="font-medium text-green-600">{userStats?.successful_applications || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--muted)]">New Jobs Today</span>
                  <span className="font-medium">{jobStats?.new_jobs_today || 0}</span>
                </div>
              </div>
            </div>

            {/* Admin badge or upgrade prompt */}
            {isAdmin ? (
              <div className="bg-[var(--night)] border border-[var(--star)] p-6 text-center">
                <div className="text-[var(--star)] text-2xl mb-2"></div>
                <h3 className="font-serif text-lg text-[#f5f2ec] mb-1">Admin Mode</h3>
                <p className="text-xs text-[rgba(245,242,236,0.5)]">
                  Unlimited applications enabled
                </p>
              </div>
            ) : user.tier === 'free' && (
              <div className="bg-[var(--night)] p-6">
                <div className="stars absolute inset-0 opacity-30" />
                <div className="relative z-10">
                  <h3 className="font-serif text-lg text-[#f5f2ec] mb-2">Upgrade to start</h3>
                  <p className="text-xs text-[rgba(245,242,236,0.5)] mb-4">
                    Choose a plan to enable automated applications
                  </p>
                  <Link href="/#pricing" className="btn-primary text-xs py-2 px-4 inline-block">
                    View Plans
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
