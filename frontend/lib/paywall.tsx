'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isPaidUser, useAuth } from './auth';

type PaywallState = {
  isLoading: boolean;
  isAuthenticated: boolean;
  isPaid: boolean;
};

/**
 * Redirects unauthenticated users to /auth/login and free/expired users
 * to /pricing. Returns the resolution state so the caller can render a
 * loading skeleton instead of flashing protected content.
 *
 * The backend re-checks /payments/subscription server-side on every
 * gated request — this hook is UX, not security.
 */
export function useRequirePaid(): PaywallState {
  const router = useRouter();
  const { user, isLoading } = useAuth();

  const authed = !!user;
  const paid = isPaidUser(user);

  useEffect(() => {
    if (isLoading) return;
    if (!authed) {
      router.replace('/auth/login?next=/pricing');
      return;
    }
    if (!paid) {
      router.replace('/pricing');
    }
  }, [isLoading, authed, paid, router]);

  return { isLoading, isAuthenticated: authed, isPaid: paid };
}

/**
 * Lighter-weight hook: just requires sign-in. Redirects anon users to
 * /auth/login with the current path as the `next` query param.
 */
export function useRequireAuth(): { isLoading: boolean; isAuthenticated: boolean } {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const authed = !!user;

  useEffect(() => {
    if (isLoading) return;
    if (!authed) {
      const next =
        typeof window !== 'undefined' ? window.location.pathname : '/dashboard';
      router.replace(`/auth/login?next=${encodeURIComponent(next)}`);
    }
  }, [isLoading, authed, router]);

  return { isLoading, isAuthenticated: authed };
}
