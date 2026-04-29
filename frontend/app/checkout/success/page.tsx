'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { isPaidUser, useAuth } from '@/lib/auth';

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 30_000;

type Phase = 'pending' | 'active' | 'timeout';

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={<SuccessShell />}>
      <CheckoutSuccessInner />
    </Suspense>
  );
}

function SuccessShell() {
  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec] flex items-center justify-center">
      <div className="text-[var(--star)] animate-pulse font-serif text-2xl">
        Loading…
      </div>
    </div>
  );
}

/**
 * Stripe redirects here after a successful Checkout. The webhook may not
 * have fired yet by the time we land — we poll /auth/me until the user
 * record reflects an active subscription, with a hard timeout fallback
 * so the page never spins forever.
 */
function CheckoutSuccessInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, refreshUser, isLoading } = useAuth();
  const [phase, setPhase] = useState<Phase>('pending');
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef<number>(Date.now());

  const sessionId = searchParams?.get('session_id') ?? null;

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      router.replace('/auth/login?next=/dashboard');
      return;
    }
    if (isPaidUser(user)) {
      setPhase('active');
      return;
    }

    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      const refreshed = await refreshUser();
      if (cancelled) return;
      if (refreshed && isPaidUser(refreshed)) {
        setPhase('active');
        return;
      }
      const sinceStart = Date.now() - startedAt.current;
      setElapsed(sinceStart);
      if (sinceStart >= POLL_TIMEOUT_MS) {
        setPhase('timeout');
        return;
      }
      window.setTimeout(tick, POLL_INTERVAL_MS);
    };
    window.setTimeout(tick, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
    };
  }, [isLoading, user, refreshUser, router]);

  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec] flex items-center justify-center px-6 relative overflow-hidden">
      <div className="stars opacity-50" />
      <div className="relative z-10 w-full max-w-md text-center">
        {phase === 'pending' && (
          <>
            <div className="font-serif text-3xl mb-3">
              Confirming your subscription…
            </div>
            <p className="text-sm text-[rgba(245,242,236,0.5)] font-light mb-8">
              Stripe is letting us know about your payment. This usually
              takes a few seconds.
            </p>
            <div className="mx-auto w-12 h-12 border-2 border-[rgba(245,242,236,0.15)] border-t-[var(--star)] rounded-full animate-spin" />
            <p className="mt-6 text-xs text-[rgba(245,242,236,0.3)] tracking-widest">
              {Math.round(elapsed / 1000)}s elapsed
            </p>
          </>
        )}

        {phase === 'active' && (
          <>
            <div className="text-[var(--star)] text-5xl mb-4 font-serif italic">
              Welcome
            </div>
            <p className="font-serif text-3xl mb-3">
              Your <span className="capitalize">{user?.tier}</span> plan is active.
            </p>
            <p className="text-sm text-[rgba(245,242,236,0.5)] font-light mb-10">
              Applications start running tonight at 10 PM. Adjust your
              preferences any time.
            </p>
            <div className="flex gap-3 justify-center flex-wrap">
              <Link href="/dashboard" className="btn-primary">
                Go to dashboard
              </Link>
              <Link
                href="/intake"
                className="btn-ghost border border-[rgba(245,242,236,0.15)]"
              >
                Edit preferences
              </Link>
            </div>
          </>
        )}

        {phase === 'timeout' && (
          <>
            <div className="font-serif text-3xl mb-3">
              Almost there.
            </div>
            <p className="text-sm text-[rgba(245,242,236,0.5)] font-light mb-8">
              Stripe is taking a little longer than usual to confirm.
              Your payment was received — your account will update within a
              few minutes. You can keep going.
            </p>
            <div className="flex gap-3 justify-center flex-wrap">
              <Link href="/dashboard" className="btn-primary">
                Go to dashboard
              </Link>
              <button
                type="button"
                onClick={() => {
                  startedAt.current = Date.now();
                  setElapsed(0);
                  setPhase('pending');
                }}
                className="btn-ghost border border-[rgba(245,242,236,0.15)]"
              >
                Check again
              </button>
            </div>
          </>
        )}

        {sessionId && (
          <p className="mt-12 text-[10px] tracking-widest text-[rgba(245,242,236,0.2)] font-mono">
            session: {sessionId.slice(0, 18)}…
          </p>
        )}
      </div>
    </div>
  );
}
