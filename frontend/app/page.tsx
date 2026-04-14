'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

const timelineSteps = [
  {
    num: '01',
    title: 'Tell us what you want',
    desc: 'Answer a quick intake quiz. Upload your resume. Set your target roles, locations, salary range, and work authorization.',
    tag: 'One time setup',
  },
  {
    num: '02',
    title: 'We find the jobs',
    desc: 'NightShift scans LinkedIn, Indeed, and more every night. Jobs are filtered against your preferences before a single application is filed.',
    tag: 'LinkedIn · Indeed · More',
  },
  {
    num: '03',
    title: 'We fill the forms',
    desc: 'Our AI reads every form field, matches your profile to the right answers, handles dropdowns, dates, and edge cases. Captchas are solved automatically.',
    tag: 'Claude AI · Playwright',
  },
  {
    num: '04',
    title: 'Wake up to results',
    desc: 'Every morning your Google Sheet updates with every job applied to — company, role, date, resume version used, and answers submitted.',
    tag: 'Google Sheets log',
  },
];

const pricingTiers = [
  {
    name: 'Starter',
    price: 19,
    features: [
      '3 applications per night',
      'LinkedIn job feed',
      'Claude AI form filling',
      'Basic Google Sheets log',
      'Captcha handling included',
    ],
  },
  {
    name: 'Pro',
    price: 39,
    featured: true,
    features: [
      '10 applications per night',
      'LinkedIn + Indeed feed',
      'Custom resume per application',
      'Full Google Sheets dashboard',
      'Captcha handling included',
      'Priority queue',
    ],
  },
  {
    name: 'Max',
    price: 69,
    features: [
      '25 applications per night',
      'All job boards',
      'Custom resume per application',
      'AI cover letter per application',
      'Advanced Sheets metrics',
      'Captcha handling included',
      'Apply within 5 min of posting',
    ],
  },
];

const addons = [
  {
    price: '+$10 / mo',
    name: 'Tailored resume',
    desc: 'AI rewrites your resume for each job posting, emphasizing the right skills for the role.',
  },
  {
    price: '+$10 / mo',
    name: 'Cover letter',
    desc: 'Generates a unique, role-specific cover letter for every application automatically.',
  },
  {
    price: '+$5 / mo',
    name: 'Advanced metrics',
    desc: 'Token usage, time to completion, site-by-site breakdown, and failure analysis in Sheets.',
  },
  {
    price: 'Coming soon',
    name: '5-minute apply',
    desc: 'Apply within 5 minutes of a job posting going live. First applicant advantage.',
  },
  {
    price: 'Coming soon',
    name: 'Smart timing',
    desc: 'ML model finds optimal application windows based on historical response rates.',
  },
  {
    price: 'Coming soon',
    name: 'Career consulting',
    desc: '1:1 strategy sessions. Resume reviews. Interview prep. The full picture.',
  },
];

export default function HomePage() {
  const [currentTime, setCurrentTime] = useState('11:00 PM');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      let h = now.getHours();
      const m = String(now.getMinutes()).padStart(2, '0');
      const ampm = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      setCurrentTime(`${h}:${m} ${ampm}`);
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-10 py-5 bg-[rgba(13,15,20,0.8)] backdrop-blur-xl border-b border-[rgba(245,242,236,0.06)]">
        <Link href="/" className="font-serif text-xl text-[#f5f2ec] italic">
          NightShift
        </Link>
        <ul className="hidden md:flex gap-8 list-none">
          <li>
            <a href="#how" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              How it works
            </a>
          </li>
          <li>
            <a href="#pricing" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              Pricing
            </a>
          </li>
          <li>
            <Link href="/about" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              About
            </Link>
          </li>
          <li>
            <Link href="/contact" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              Contact
            </Link>
          </li>
        </ul>
        <Link href="/auth/signup" className="btn-primary text-xs py-2.5 px-6">
          Get started
        </Link>
      </nav>

      {/* Hero */}
      <section className="min-h-screen bg-[var(--night)] flex flex-col items-center justify-center relative overflow-hidden px-6 py-20">
        <div className="stars" />
        <div className="absolute top-28 right-32 w-[72px] h-[72px] rounded-full bg-[#f0e8c8] shadow-[0_0_40px_rgba(240,232,200,0.3),0_0_80px_rgba(240,232,200,0.1)] animate-moonrise" />

        <span className="font-mono text-[11px] font-normal tracking-[0.15em] text-[var(--star)] uppercase mb-8 animate-fadein-delay-1">
          Autonomous job applications
        </span>

        <h1 className="font-serif text-[clamp(52px,8vw,96px)] font-normal text-[#f5f2ec] text-center leading-[1.05] tracking-tight max-w-[900px] animate-fadein-delay-2">
          We apply to jobs for you
          <br />
          <em className="italic text-[var(--star)]">while you sleep</em>
        </h1>

        <p className="text-sm font-light text-[rgba(245,242,236,0.5)] text-center mt-7 tracking-wide animate-fadein-delay-3">
          Set your preferences once. Wake up to submitted applications every morning.
        </p>

        <div className="mt-14 flex gap-4 flex-wrap justify-center animate-fadein-delay-4">
          <Link href="/auth/signup" className="btn-primary">
            Start applying tonight
          </Link>
          <a href="#how" className="btn-ghost">
            See how it works
          </a>
        </div>

        <span className="absolute bottom-10 left-1/2 -translate-x-1/2 text-[rgba(245,242,236,0.2)] text-[11px] tracking-widest animate-pulse-slow">
          scroll
        </span>
      </section>

      {/* Ticker */}
      <div className="bg-[var(--star)] py-2.5 overflow-hidden whitespace-nowrap">
        <div className="inline-block animate-ticker text-[11px] font-medium tracking-widest text-[var(--night)]">
          &nbsp;&nbsp;&nbsp;Applications submitted last night: 2,847&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Avg time per application: 4m 12s&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Success rate: 98.3%&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Companies reached: Stripe · Ramp · Figma · Plaid · Robinhood · Brex · Linear · Notion&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Applications submitted last night: 2,847&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Avg time per application: 4m 12s&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Success rate: 98.3%&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;Companies reached: Stripe · Ramp · Figma · Plaid · Robinhood · Brex · Linear · Notion&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;
        </div>
      </div>

      {/* How It Works */}
      <section id="how" className="py-24 px-6 max-w-[1100px] mx-auto">
        <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--muted)] mb-4">
          How it works
        </p>
        <h2 className="font-serif text-[clamp(36px,5vw,56px)] font-normal leading-[1.1] tracking-tight mb-16">
          Set up once.
          <br />
          Sleep every night.
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-px bg-[var(--border)] border border-[var(--border)]">
          {timelineSteps.map((step) => (
            <div key={step.num} className="bg-[var(--card)] p-10">
              <span className="text-[11px] tracking-widest text-[var(--muted)] mb-5 block">
                {step.num}
              </span>
              <h3 className="font-serif text-[22px] font-normal mb-3 leading-tight">
                {step.title}
              </h3>
              <p className="text-[13px] font-light text-[var(--muted)] leading-relaxed">
                {step.desc}
              </p>
              <span className="inline-block mt-5 text-[10px] tracking-widest uppercase text-[var(--star)] bg-[rgba(200,185,122,0.1)] px-2.5 py-1 border border-[rgba(200,185,122,0.2)]">
                {step.tag}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Divider */}
      <div className="h-px bg-[var(--border)]" />

      {/* Night Strip with Clock */}
      <div className="bg-[var(--night)] py-20 px-6 text-center relative overflow-hidden">
        <div className="stars opacity-40" />
        <div className="font-mono text-7xl font-light text-[var(--star)] relative z-10 mb-2 tracking-tighter">
          {currentTime}
        </div>
        <h2 className="font-serif text-[clamp(28px,4vw,48px)] text-[#f5f2ec] font-normal relative z-10 mb-4">
          NightShift clocks in.
        </h2>
        <p className="text-[rgba(245,242,236,0.4)] text-[13px] font-light relative z-10">
          Your bot starts running while you wind down.
        </p>
      </div>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6 max-w-[1100px] mx-auto">
        <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--muted)] mb-4">
          Pricing
        </p>
        <h2 className="font-serif text-[clamp(36px,5vw,56px)] font-normal leading-[1.1] tracking-tight mb-12">
          Pay for what you use.
          <br />
          Cancel anytime.
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {pricingTiers.map((tier) => (
            <div
              key={tier.name}
              className={`pricing-card relative p-10 ${
                tier.featured
                  ? 'border-[var(--star)] bg-[var(--night)] text-[#f5f2ec]'
                  : 'border-[var(--border)] bg-[var(--card)]'
              } border`}
            >
              {tier.featured && (
                <span className="absolute -top-px left-9 bg-[var(--star)] text-[var(--night)] text-[10px] font-medium tracking-widest uppercase px-3 py-1">
                  Most popular
                </span>
              )}
              <p className={`text-[11px] tracking-[0.15em] uppercase mb-5 ${tier.featured ? 'text-[rgba(245,242,236,0.4)]' : 'text-[var(--muted)]'}`}>
                {tier.name}
              </p>
              <div className="font-serif text-[52px] font-normal leading-none tracking-tight mb-1">
                ${tier.price}
              </div>
              <p className={`text-xs font-light mb-8 ${tier.featured ? 'text-[rgba(245,242,236,0.4)]' : 'text-[var(--muted)]'}`}>
                per month
              </p>
              <ul className="flex flex-col gap-3 mb-9">
                {tier.features.map((feature) => (
                  <li
                    key={feature}
                    className={`text-[13px] font-light flex gap-2.5 items-start leading-relaxed ${
                      tier.featured ? 'text-[rgba(245,242,236,0.6)]' : 'text-[var(--muted)]'
                    }`}
                  >
                    <span className="text-[var(--star)] flex-shrink-0 mt-0.5"></span>
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                href="/auth/signup"
                className="btn-primary block text-center w-full"
              >
                Get started
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Add-ons */}
      <section id="addons" className="bg-[var(--ink)] py-20 px-6">
        <div className="max-w-[1100px] mx-auto">
          <h2 className="font-serif text-[clamp(32px,4vw,48px)] text-[#f5f2ec] font-normal mb-12">
            Add-ons
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[rgba(245,242,236,0.08)]">
            {addons.map((addon) => (
              <div
                key={addon.name}
                className="bg-[var(--ink)] p-8 border border-[rgba(245,242,236,0.06)]"
              >
                <p className="text-[11px] text-[var(--star)] tracking-widest mb-3">
                  {addon.price}
                </p>
                <h3 className="font-serif text-xl text-[#f5f2ec] font-normal mb-2">
                  {addon.name}
                </h3>
                <p className="text-xs text-[rgba(245,242,236,0.35)] font-light leading-relaxed">
                  {addon.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--night)] py-12 px-6 text-center border-t border-[rgba(245,242,236,0.06)]">
        <div className="font-serif text-2xl text-[#f5f2ec] italic mb-3">
          NightShift
        </div>
        <p className="text-xs text-[rgba(245,242,236,0.25)] font-light">
          We apply to jobs for you while you sleep.
        </p>
        <p className="text-xs text-[rgba(245,242,236,0.25)] font-light mt-2">
          © 2026 NightShift · Privacy · Terms
        </p>
      </footer>
    </div>
  );
}
