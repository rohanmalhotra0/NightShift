/**
 * Auth utilities and context
 */

'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { auth as authApi, setPaywallHandler, ApiError } from './api';

type User = {
  id: string;
  email: string;
  tier: string;
  is_admin: boolean;
  subscription_status: string | null;
  current_period_end: string | null;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
};

// Subscription statuses that grant access. Mirrors the backend's set in
// api/auth.py::_PAID_ACCESS_STATUSES — kept in sync manually.
const PAID_ACCESS_STATUSES = new Set(['active', 'trialing', 'past_due']);

export function isPaidUser(user: User | null): boolean {
  if (!user) return false;
  if (user.is_admin) return true;
  if (user.tier === 'free') return false;
  return user.subscription_status
    ? PAID_ACCESS_STATUSES.has(user.subscription_status)
    : false;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'nightshift_token';

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (storedToken) {
      setToken(storedToken);
      authApi.getMe(storedToken)
        .then(setUser)
        .catch(() => {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  // Globally redirect to /pricing whenever any API call returns 402
  // with `upgrade_url`. Each consumer would otherwise need its own
  // try/catch — wiring it once here means new gated endpoints get
  // the same UX for free.
  useEffect(() => {
    setPaywallHandler((error: ApiError) => {
      if (typeof window === 'undefined') return false;
      const target = error.upgradeUrl || '/pricing';
      const path = window.location.pathname;
      // Don't redirect away from /pricing itself or /auth/* — the user
      // is already where they need to be (or about to authenticate).
      if (path.startsWith(target) || path.startsWith('/auth/')) {
        return false;
      }
      const sep = target.includes('?') ? '&' : '?';
      router.push(`${target}${sep}from=gate`);
      return true;
    });
    return () => setPaywallHandler(null);
  }, [router]);

  const login = async (email: string, password: string) => {
    const { access_token } = await authApi.login(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    const userData = await authApi.getMe(access_token);
    setUser(userData);
  };

  const signup = async (email: string, password: string) => {
    const { access_token } = await authApi.signup(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    const userData = await authApi.getMe(access_token);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const refreshUser = async (): Promise<User | null> => {
    const t = token ?? localStorage.getItem(TOKEN_KEY);
    if (!t) return null;
    try {
      const userData = await authApi.getMe(t);
      setUser(userData);
      return userData;
    } catch {
      return null;
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, signup, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
