'use client';

import Link from 'next/link';

export default function CheckoutCancelPage() {
  return (
    <div className="min-h-screen bg-[var(--night)] text-[#f5f2ec] flex items-center justify-center px-6 relative overflow-hidden">
      <div className="stars opacity-50" />
      <div className="relative z-10 w-full max-w-md text-center">
        <p className="text-[11px] tracking-[0.15em] uppercase text-[rgba(245,242,236,0.4)] mb-3">
          Checkout cancelled
        </p>
        <h1 className="font-serif text-3xl mb-4">No worries.</h1>
        <p className="text-sm text-[rgba(245,242,236,0.5)] font-light mb-10">
          Your card wasn&apos;t charged. You can pick a different plan, or
          come back later — your account is still here.
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link href="/pricing" className="btn-primary">
            Back to plans
          </Link>
          <Link
            href="/dashboard"
            className="btn-ghost border border-[rgba(245,242,236,0.15)]"
          >
            Skip for now
          </Link>
        </div>
      </div>
    </div>
  );
}
