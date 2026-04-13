'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Moon,
  BarChart3,
  Briefcase,
  CheckCircle,
  XCircle,
  Clock,
  ExternalLink,
  Settings,
  LogOut,
  FileSpreadsheet,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import { useAuth } from '@/lib/auth';
import { applications, jobs, users } from '@/lib/api';
import { formatDate, formatCurrency } from '@/lib/utils';

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

  const handleCreateSheet = async () => {
    if (!token) return;
    try {
      const result = await users.createSheet(token);
      setSheetsUrl(result.url);
    } catch (error) {
      console.error('Failed to create sheet:', error);
    }
  };

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'submitted':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'pending':
      case 'in_progress':
        return <Clock className="h-5 w-5 text-yellow-500" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Moon className="h-7 w-7 text-primary-600" />
            <span className="text-lg font-bold text-gray-900">NightShift</span>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">{user.email}</span>
            <span className="px-2 py-1 text-xs font-medium bg-primary-100 text-primary-700 rounded-full capitalize">
              {user.tier}
            </span>
            <Link href="/intake">
              <Button variant="ghost" size="sm">
                <Settings className="h-4 w-4" />
              </Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">
        {/* Stats grid */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Today&apos;s Applications</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {todayStats?.submitted || 0}
                    <span className="text-sm font-normal text-gray-400">
                      /{todayStats?.daily_limit || 0}
                    </span>
                  </p>
                </div>
                <div className="p-3 bg-primary-100 rounded-lg">
                  <CheckCircle className="h-6 w-6 text-primary-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Matching Jobs</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {jobStats?.unapplied_matching || 0}
                  </p>
                </div>
                <div className="p-3 bg-blue-100 rounded-lg">
                  <Briefcase className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Success Rate (30d)</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {userStats ? `${Math.round(userStats.success_rate * 100)}%` : '0%'}
                  </p>
                </div>
                <div className="p-3 bg-green-100 rounded-lg">
                  <BarChart3 className="h-6 w-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Total Cost (30d)</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {userStats ? formatCurrency(userStats.total_cost) : '$0.00'}
                  </p>
                </div>
                <div className="p-3 bg-purple-100 rounded-lg">
                  <BarChart3 className="h-6 w-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Recent applications */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Recent Applications</CardTitle>
                <Link href="/applications">
                  <Button variant="ghost" size="sm">
                    View all
                  </Button>
                </Link>
              </CardHeader>
              <CardContent className="p-0">
                {recentApps.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Briefcase className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                    <p>No applications yet</p>
                    <p className="text-sm mt-1">
                      Applications will start running tonight at 10 PM
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {recentApps.map((app) => (
                      <div key={app.id} className="px-6 py-4 flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          {statusIcon(app.status)}
                          <div>
                            <p className="font-medium text-gray-900">{app.job_title}</p>
                            <p className="text-sm text-gray-500">{app.company}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-gray-500 capitalize">{app.status}</p>
                          <p className="text-xs text-gray-400">
                            {formatDate(app.submitted_at || app.queued_at)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Side panel */}
          <div className="space-y-6">
            {/* Google Sheets */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <FileSpreadsheet className="h-5 w-5" />
                  <span>Application Log</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {sheetsUrl ? (
                  <a
                    href={sheetsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-3 bg-green-50 rounded-lg text-green-700 hover:bg-green-100 transition-colors"
                  >
                    <span className="text-sm font-medium">View in Google Sheets</span>
                    <ExternalLink className="h-4 w-4" />
                  </a>
                ) : (
                  <div className="text-center">
                    <p className="text-sm text-gray-500 mb-3">
                      Track all applications in Google Sheets
                    </p>
                    <Button onClick={handleCreateSheet} size="sm">
                      Create Sheet
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick stats */}
            <Card>
              <CardHeader>
                <CardTitle>30-Day Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Total Applications</span>
                  <span className="font-medium">{userStats?.total_applications || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Successful</span>
                  <span className="font-medium text-green-600">
                    {userStats?.successful_applications || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">New Jobs Today</span>
                  <span className="font-medium">{jobStats?.new_jobs_today || 0}</span>
                </div>
              </CardContent>
            </Card>

            {/* Upgrade prompt for free tier */}
            {user.tier === 'free' && (
              <Card className="bg-gradient-to-br from-primary-500 to-primary-700 text-white">
                <CardContent className="p-6">
                  <h3 className="font-semibold text-lg mb-2">Upgrade to start applying</h3>
                  <p className="text-sm text-primary-100 mb-4">
                    Choose a plan to enable automated applications
                  </p>
                  <Link href="/#pricing">
                    <Button variant="secondary" size="sm">
                      View Plans
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
