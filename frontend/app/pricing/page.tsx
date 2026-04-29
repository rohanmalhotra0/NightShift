'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError, payments } from '@/lib/api';
import { isPaidUser, useAuth } from '@/lib/auth';

type Tier = {
  id: string;
  name: string;
  price: number;
  apps_per_night: number;
  features: string[];
};

const FEATURED_TIER_ID = 'pro';

export default function PricingPage() {
  return (
    <Suspense fallback={<PricingShell />}>
      <PricingPageInner />
    </Suspense>
  );
}

function PricingPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, token, isLoading } = useAuth();

  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [loadingTier, setLoadingTier] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fromGate = searchParams?.get('from') === 'gate';

  useEffect(() => {
    payments
      .pricing()
      .then((data) => setTiers(data.tiers as Tier[]))
      .catch((e) => {
        const message = e instanceof Error ? e.message : 'Failed to load plans';
        setError(message);
      });
  }, []);

  const handleUpgrade = async (tierId: string) => {
    setError(null);
    if (!user || !token) {
      router.push(`/auth/signup?next=${encodeURIComponent(`/pricing?tier=${tierId}`)}`);
      return;
    }
    setLoadingTier(tierId);
    try {
      const origin =
        typeof window !== 'undefined' ? window.location.origin : '';
      const successUrl = `${origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`;
      const cancelUrl = `${origin}/checkout/cancel`;
      const { checkout_url } = await payments.checkout(
        token,
        tierId,
        successUrl,
        cancelUrl
      );
      window.location.assign(checkout_url);
    } catch (e: unknown) {
      let message: string;
      if (e instanceof ApiError) {
        if (e.status === 503) {
          message =
            'This plan isn’t available yet — the price ID hasn’t been wired up. Try a different tier.';
        } else if (e.status === 401 || e.status === 403) {
          router.push('/auth/login?next=/pricing');
          return;
        } else {
          message = e.message;
        }
      } else {
        message = e instanceof Error ? e.message : 'Failed to start checkout';
      }
      setError(message);
    } finally {
      setLoadingTier(null);
    }
  };

  const alreadyPaid = isPaidUser(user);

  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec]">
      <div className="stars opacity-40 fixed inset-0" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-10 py-5 border-b border-[rgba(245,242,236,0.06)]">
        <Link href="/" className="font-serif text-xl italic">
          NightShift
        </Link>
        <div className="flex items-center gap-6 text-xs text-[rgba(245,242,236,0.4)]">
          {user ? (
            <Link href="/dashboard" className="hover:text-[#f5f2ec]">
              Dashboard
            </Link>
          ) : (
            <>
              <Link href="/auth/login" className="hover:text-[#f5f2ec]">
                Sign in
              </Link>
              <Link href="/auth/signup" className="btn-primary text-xs py-2.5 px-6">
                Get started
              </Link>
            </>
          )}
        </div>
      </nav>

      <main className="relative z-10 max-w-[1100px] mx-auto px-6 py-20">
        {fromGate && !alreadyPaid && (
          <div className="mb-10 border border-[var(--star)] bg-[rgba(200,185,122,0.08)] p-5 text-sm">
            <p className="text-[var(--star)] tracking-widest text-[11px] uppercase mb-1">
              Subscription required
            </p>
            <p className="text-[rgba(245,242,236,0.7)]">
              That feature is paid-only. Pick a plan below to enable it.
            </p>
          </div>
        )}

        <p className="text-[11px] tracking-[0.15em] uppercase text-[rgba(245,242,236,0.4)] mb-4">
          Pricing
        </p>
        <h1 className="font-serif text-[clamp(40px,5vw,64px)] leading-[1.1] tracking-tight mb-4">
          Pay for what you use.
          <br />
          <em className="italic text-[var(--star)]">Cancel anytime.</em>
        </h1>
        <p className="text-[rgba(245,242,236,0.5)] text-sm font-light mb-12 max-w-xl">
          All plans include automated nightly applications, AI-powered form
          filling, and a Google Sheets log of every submission.
        </p>

        {alreadyPaid && (
          <div className="mb-10 border border-[rgba(245,242,236,0.1)] bg-[rgba(245,242,236,0.03)] p-5 text-sm flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="tracking-widest text-[11px] uppercase text-[var(--star)] mb-1">
                Current plan
              </p>
              <p className="text-[rgba(245,242,236,0.85)]">
                You&apos;re on the <strong className="capitalize">{user?.tier}</strong> plan
                {user?.subscription_status ? ` (${user.subscription_status})` : ''}.
              </p>
            </div>
            <Link
              href="/dashboard"
              className="text-xs text-[var(--star)] hover:underline"
            >
              Back to dashboard
            </Link>
          </div>
        )}

        {error && (
          <div className="mb-8 p-4 border border-red-500/30 bg-red-500/10 text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers === null ? (
            <SkeletonTiers />
          ) : (
            tiers.map((tier) => {
              const featured = tier.id === FEATURED_TIER_ID;
              const isCurrent = user?.tier === tier.id && alreadyPaid;
              return (
                <div
                  key={tier.id}
                  className={`relative p-10 border ${
                    featured
                      ? 'border-[var(--star)] bg-[rgba(200,185,122,0.04)]'
                      : 'border-[rgba(245,242,236,0.1)] bg-[rgba(13,15,20,0.6)]'
                  }`}
                >
                  {featured && (
                    <span className="absolute -top-px left-9 bg-[var(--star)] text-[var(--night)] text-[10px] font-medium tracking-widest uppercase px-3 py-1">
                      Most popular
                    </span>
                  )}
                  <p className="text-[11px] tracking-[0.15em] uppercase text-[rgba(245,242,236,0.4)] mb-5">
                    {tier.name}
                  </p>
                  <div className="font-serif text-[52px] leading-none tracking-tight mb-1">
                    ${tier.price}
                  </div>
                  <p className="text-xs font-light text-[rgba(245,242,236,0.4)] mb-8">
                    per month
                  </p>
                  <ul className="flex flex-col gap-3 mb-9">
                    {tier.features.map((feature) => (
                      <li
                        key={feature}
                        className="text-[13px] font-light flex gap-2.5 items-start leading-relaxed text-[rgba(245,242,236,0.6)]"
                      >
                        <span className="text-[var(--star)] flex-shrink-0 mt-0.5">·</span>
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={() => handleUpgrade(tier.id)}
                    disabled={
                      loadingTier !== null ||
                      isLoading ||
                      isCurrent
                    }
                    className="btn-primary block text-center w-full disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isCurrent
                      ? 'Current plan'
                      : loadingTier === tier.id
                      ? 'Redirecting…'
                      : user
                      ? 'Upgrade'
                      : 'Get started'}
                  </button>
                </div>
              );
            })
          )}
        </div>

        <p className="mt-14 text-xs text-[rgba(245,242,236,0.3)] text-center">
          Test mode · prices subject to change · cancel anytime from your account.
        </p>
      </main>
    </div>
  );
}

function PricingShell() {
  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec] flex items-center justify-center">
      <div className="text-[var(--star)] animate-pulse font-serif text-2xl">
        Loading…
      </div>
    </div>
  );
}

function SkeletonTiers() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="p-10 border border-[rgba(245,242,236,0.05)] bg-[rgba(13,15,20,0.4)] animate-pulse"
        >
          <div className="h-3 w-20 bg-[rgba(245,242,236,0.08)] mb-5" />
          <div className="h-12 w-32 bg-[rgba(245,242,236,0.08)] mb-2" />
          <div className="h-3 w-20 bg-[rgba(245,242,236,0.06)] mb-8" />
          <div className="space-y-3 mb-9">
            <div className="h-3 w-full bg-[rgba(245,242,236,0.05)]" />
            <div className="h-3 w-5/6 bg-[rgba(245,242,236,0.05)]" />
            <div className="h-3 w-4/6 bg-[rgba(245,242,236,0.05)]" />
          </div>
          <div className="h-10 bg-[rgba(245,242,236,0.06)]" />
        </div>
      ))}
    </>
  );
}
