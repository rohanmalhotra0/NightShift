'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ApiError, payments } from '@/lib/api';
import { isPaidUser, useAuth } from '@/lib/auth';

type Subscription = {
  tier: string;
  status: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
};

type ActionState = 'idle' | 'cancel' | 'resume' | 'portal';

export default function BillingPage() {
  const router = useRouter();
  const { user, token, isLoading, refreshUser } = useAuth();

  const [sub, setSub] = useState<Subscription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<ActionState>('idle');
  const [confirmCancel, setConfirmCancel] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    if (!token) {
      router.replace('/auth/login?next=/account/billing');
      return;
    }
    payments
      .subscription(token)
      .then(setSub)
      .catch((e) => {
        const message = e instanceof Error ? e.message : 'Failed to load subscription';
        setError(message);
      });
  }, [isLoading, token, router]);

  const reload = async () => {
    if (!token) return;
    try {
      const next = await payments.subscription(token);
      setSub(next);
    } catch {
      /* surfaced via the action error path */
    }
    await refreshUser();
  };

  const handleCancel = async () => {
    if (!token) return;
    setError(null);
    setPending('cancel');
    try {
      await payments.cancel(token);
      await reload();
      setConfirmCancel(false);
    } catch (e) {
      setError(humanizeError(e, 'Failed to cancel subscription'));
    } finally {
      setPending('idle');
    }
  };

  const handleResume = async () => {
    if (!token) return;
    setError(null);
    setPending('resume');
    try {
      await payments.resume(token);
      await reload();
    } catch (e) {
      setError(humanizeError(e, 'Failed to resume subscription'));
    } finally {
      setPending('idle');
    }
  };

  const handleOpenPortal = async () => {
    if (!token) return;
    setError(null);
    setPending('portal');
    try {
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const { url } = await payments.portal(
        token,
        `${origin}/account/billing`
      );
      window.location.assign(url);
    } catch (e) {
      setError(humanizeError(e, 'Failed to open billing portal'));
      setPending('idle');
    }
  };

  if (isLoading || (!user && token)) {
    return (
      <div className="min-h-screen bg-[var(--night)] flex items-center justify-center">
        <div className="text-[var(--star)] animate-pulse font-serif text-2xl">Loading…</div>
      </div>
    );
  }

  if (!user) return null;

  const paid = isPaidUser(user);
  const periodEnd = sub?.current_period_end
    ? new Date(sub.current_period_end)
    : null;
  const periodEndFormatted = periodEnd
    ? periodEnd.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  const showCancelScheduled = sub?.cancel_at_period_end && paid;

  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec] relative">
      <div className="stars opacity-30 fixed inset-0" />

      <nav className="relative z-10 flex items-center justify-between px-10 py-5 border-b border-[rgba(245,242,236,0.06)]">
        <Link href="/" className="font-serif text-xl italic">
          NightShift
        </Link>
        <div className="flex items-center gap-6 text-xs text-[rgba(245,242,236,0.4)]">
          <Link href="/dashboard" className="hover:text-[#f5f2ec]">
            Dashboard
          </Link>
          <span>{user.email}</span>
        </div>
      </nav>

      <main className="relative z-10 max-w-3xl mx-auto px-6 py-16">
        <p className="text-[11px] tracking-[0.15em] uppercase text-[rgba(245,242,236,0.4)] mb-3">
          Account
        </p>
        <h1 className="font-serif text-[clamp(36px,4vw,52px)] leading-[1.1] tracking-tight mb-3">
          Billing
        </h1>
        <p className="text-[rgba(245,242,236,0.5)] text-sm font-light mb-12 max-w-xl">
          Manage your subscription, invoices, and payment method.
        </p>

        {error && (
          <div className="mb-8 p-4 border border-red-500/30 bg-red-500/10 text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Plan card */}
        <section className="mb-8 border border-[rgba(245,242,236,0.1)] bg-[rgba(13,15,20,0.6)]">
          <div className="px-7 py-6 border-b border-[rgba(245,242,236,0.06)]">
            <p className="text-[11px] tracking-widest uppercase text-[var(--star)] mb-1">
              Current plan
            </p>
            <div className="flex items-baseline gap-3 flex-wrap">
              <span className="font-serif text-3xl capitalize">
                {sub?.tier || user.tier}
              </span>
              <StatusPill status={sub?.status} paid={paid} />
            </div>
          </div>

          <div className="px-7 py-6 grid sm:grid-cols-2 gap-6 text-sm">
            <Field label="Status" value={statusLabel(sub?.status, paid)} />
            <Field
              label={
                showCancelScheduled
                  ? 'Access until'
                  : sub?.status === 'past_due'
                  ? 'Charge retry by'
                  : 'Renews on'
              }
              value={periodEndFormatted || '—'}
            />
          </div>

          {showCancelScheduled && (
            <div className="mx-7 mb-6 p-4 border border-[rgba(200,185,122,0.3)] bg-[rgba(200,185,122,0.06)] text-sm">
              <p className="text-[var(--star)] mb-1">Cancellation scheduled</p>
              <p className="text-[rgba(245,242,236,0.6)] text-xs leading-relaxed">
                You&apos;ll keep <strong className="capitalize">{user.tier}</strong> features
                {periodEndFormatted ? ` until ${periodEndFormatted}` : ''}, then
                drop to free. Resume any time before then to stay on.
              </p>
            </div>
          )}
        </section>

        {/* Actions */}
        <section className="grid sm:grid-cols-2 gap-4 mb-8">
          {paid && !showCancelScheduled && (
            <ActionCard
              title="Cancel subscription"
              description="Keep access until the end of the current billing period."
              actionLabel={
                pending === 'cancel'
                  ? 'Cancelling…'
                  : confirmCancel
                  ? 'Confirm cancel'
                  : 'Cancel plan'
              }
              onAction={confirmCancel ? handleCancel : () => setConfirmCancel(true)}
              danger
              disabled={pending !== 'idle'}
              secondary={
                confirmCancel ? (
                  <button
                    type="button"
                    onClick={() => setConfirmCancel(false)}
                    className="text-xs text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.8)]"
                  >
                    Keep my plan
                  </button>
                ) : null
              }
            />
          )}

          {showCancelScheduled && (
            <ActionCard
              title="Resume subscription"
              description="Undo the pending cancellation and keep applying."
              actionLabel={pending === 'resume' ? 'Resuming…' : 'Resume plan'}
              onAction={handleResume}
              disabled={pending !== 'idle'}
            />
          )}

          {!paid && (
            <ActionCard
              title="Upgrade"
              description="Unlock automated nightly applications."
              actionLabel="View plans"
              onAction={() => router.push('/pricing')}
              disabled={pending !== 'idle'}
              primary
            />
          )}

          <ActionCard
            title="Manage billing on Stripe"
            description="Update card, download invoices, change plan."
            actionLabel={pending === 'portal' ? 'Opening…' : 'Open Stripe portal'}
            onAction={handleOpenPortal}
            disabled={pending !== 'idle'}
          />
        </section>

        <p className="text-xs text-[rgba(245,242,236,0.3)] text-center">
          Need help?{' '}
          <Link href="/contact" className="text-[var(--star)] hover:underline">
            Contact us
          </Link>
        </p>
      </main>
    </div>
  );
}

function StatusPill({
  status,
  paid,
}: {
  status: string | null | undefined;
  paid: boolean;
}) {
  const label = statusLabel(status, paid);
  const tone =
    status === 'active' || status === 'trialing'
      ? 'bg-[rgba(112,182,118,0.15)] text-green-300 border-green-300/30'
      : status === 'past_due'
      ? 'bg-[rgba(200,185,122,0.15)] text-[var(--star)] border-[var(--star)]/30'
      : 'bg-[rgba(245,242,236,0.06)] text-[rgba(245,242,236,0.5)] border-[rgba(245,242,236,0.15)]';
  return (
    <span
      className={`text-[10px] tracking-widest uppercase px-2 py-1 border ${tone}`}
    >
      {label}
    </span>
  );
}

function statusLabel(
  status: string | null | undefined,
  paid: boolean
): string {
  if (!status) return paid ? 'Active' : 'Free';
  switch (status) {
    case 'active':
      return 'Active';
    case 'trialing':
      return 'Trial';
    case 'past_due':
      return 'Payment retrying';
    case 'canceled':
      return 'Canceled';
    case 'incomplete':
    case 'incomplete_expired':
      return 'Incomplete';
    case 'unpaid':
      return 'Unpaid';
    default:
      return status;
  }
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-1">
        {label}
      </p>
      <p className="text-[rgba(245,242,236,0.85)]">{value}</p>
    </div>
  );
}

function ActionCard({
  title,
  description,
  actionLabel,
  onAction,
  disabled,
  danger,
  primary,
  secondary,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
  disabled?: boolean;
  danger?: boolean;
  primary?: boolean;
  secondary?: React.ReactNode;
}) {
  const buttonClasses = danger
    ? 'border border-red-400/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed'
    : primary
    ? 'btn-primary disabled:opacity-50 disabled:cursor-not-allowed'
    : 'border border-[rgba(245,242,236,0.2)] text-[rgba(245,242,236,0.8)] hover:border-[var(--star)] hover:text-[var(--star)] disabled:opacity-50 disabled:cursor-not-allowed';
  return (
    <div className="border border-[rgba(245,242,236,0.08)] bg-[rgba(13,15,20,0.4)] p-6">
      <h3 className="font-serif text-lg mb-2">{title}</h3>
      <p className="text-xs text-[rgba(245,242,236,0.5)] font-light leading-relaxed mb-5">
        {description}
      </p>
      <div className="flex items-center gap-4 flex-wrap">
        <button
          type="button"
          onClick={onAction}
          disabled={disabled}
          className={`px-5 py-2.5 text-xs tracking-widest uppercase ${buttonClasses}`}
        >
          {actionLabel}
        </button>
        {secondary}
      </div>
    </div>
  );
}

function humanizeError(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    if (e.status === 401 || e.status === 403) {
      return 'Your session expired. Please sign in again.';
    }
    return e.message || fallback;
  }
  return e instanceof Error ? e.message : fallback;
}
