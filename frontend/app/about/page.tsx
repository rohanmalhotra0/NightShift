'use client';

import Link from 'next/link';

const team = [
  {
    name: 'The Bot',
    role: 'Chief Application Officer',
    desc: 'Works the night shift. Never sleeps. Never complains. Applies to jobs with unwavering dedication.',
  },
  {
    name: 'Claude AI',
    role: 'Form Whisperer',
    desc: 'Reads every question, understands context, and fills forms like a human would — but faster.',
  },
  {
    name: 'The Scheduler',
    role: 'Time Lord',
    desc: 'Knows exactly when to clock in. Coordinates nightly runs with precision.',
  },
];

const values = [
  {
    title: 'Sleep is productive',
    desc: 'Your 8 hours of rest should work for you. We believe in maximizing every hour of your job search.',
  },
  {
    title: 'Quality over quantity',
    desc: 'We don\'t spam applications. Every submission is carefully matched to your preferences and filled with care.',
  },
  {
    title: 'Transparency first',
    desc: 'Every application is logged. Every action is tracked. You always know exactly what we did.',
  },
  {
    title: 'Time is money',
    desc: 'The average job application takes 30 minutes. We do it in 4. That\'s time you get back.',
  },
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-10 py-5 bg-[rgba(13,15,20,0.8)] backdrop-blur-xl border-b border-[rgba(245,242,236,0.06)]">
        <Link href="/" className="font-serif text-xl text-[#f5f2ec] italic">
          NightShift
        </Link>
        <ul className="hidden md:flex gap-8 list-none">
          <li>
            <Link href="/#how" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              How it works
            </Link>
          </li>
          <li>
            <Link href="/#pricing" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              Pricing
            </Link>
          </li>
          <li>
            <Link href="/about" className="text-xs text-[rgba(245,242,236,0.9)] tracking-wide">
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
      <section className="bg-[var(--night)] pt-32 pb-24 px-6 relative overflow-hidden">
        <div className="stars" />
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--star)] mb-6">
            About NightShift
          </p>
          <h1 className="font-serif text-[clamp(40px,6vw,72px)] font-normal text-[#f5f2ec] leading-tight mb-6">
            We believe job hunting<br />
            <em className="italic text-[var(--star)]">shouldn't be a full-time job</em>
          </h1>
          <p className="text-[rgba(245,242,236,0.5)] text-base font-light max-w-2xl mx-auto">
            NightShift was built for people tired of spending hours filling out the same forms over and over. We automate the tedious parts so you can focus on what matters: preparing for interviews and choosing the right opportunity.
          </p>
        </div>
      </section>

      {/* Stats Strip */}
      <div className="bg-[var(--star)] py-8 px-6">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <div className="font-serif text-4xl text-[var(--night)]">50K+</div>
            <div className="text-[11px] tracking-widest uppercase text-[var(--night)] opacity-60 mt-1">Applications Sent</div>
          </div>
          <div>
            <div className="font-serif text-4xl text-[var(--night)]">98.3%</div>
            <div className="text-[11px] tracking-widest uppercase text-[var(--night)] opacity-60 mt-1">Success Rate</div>
          </div>
          <div>
            <div className="font-serif text-4xl text-[var(--night)]">4m 12s</div>
            <div className="text-[11px] tracking-widest uppercase text-[var(--night)] opacity-60 mt-1">Avg Per App</div>
          </div>
          <div>
            <div className="font-serif text-4xl text-[var(--night)]">2,000+</div>
            <div className="text-[11px] tracking-widest uppercase text-[var(--night)] opacity-60 mt-1">Happy Users</div>
          </div>
        </div>
      </div>

      {/* Our Story */}
      <section className="py-24 px-6">
        <div className="max-w-3xl mx-auto">
          <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--muted)] mb-4">
            Our Story
          </p>
          <h2 className="font-serif text-[clamp(32px,4vw,48px)] font-normal leading-tight mb-8">
            Born from frustration
          </h2>
          <div className="space-y-6 text-[var(--muted)] font-light leading-relaxed">
            <p>
              It started with a spreadsheet. Hundreds of rows of jobs applied to, dates tracked, follow-ups scheduled. Hours spent every day filling out the same information: name, email, phone, work authorization, salary expectations.
            </p>
            <p>
              We asked ourselves: why does every company need me to type my address again? Why can't this be automated? Why am I spending 4 hours a day on applications when I could be practicing for interviews?
            </p>
            <p>
              So we built NightShift. A bot that understands job applications, powered by AI that can read forms like a human. It works while you sleep, applying to jobs that match your criteria, filling every field correctly, handling CAPTCHAs, and logging everything to a spreadsheet.
            </p>
            <p>
              Now you can wake up to a list of jobs applied to overnight. Check your Google Sheet. Prepare for callbacks. That's the NightShift way.
            </p>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="py-24 px-6 bg-[var(--night)]">
        <div className="max-w-5xl mx-auto">
          <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--star)] mb-4">
            Our Values
          </p>
          <h2 className="font-serif text-[clamp(32px,4vw,48px)] font-normal text-[#f5f2ec] leading-tight mb-12">
            What we believe
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {values.map((value) => (
              <div key={value.title} className="border border-[rgba(245,242,236,0.1)] p-8">
                <h3 className="font-serif text-xl text-[#f5f2ec] mb-3">{value.title}</h3>
                <p className="text-[rgba(245,242,236,0.5)] text-sm font-light leading-relaxed">
                  {value.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--muted)] mb-4">
            The Team
          </p>
          <h2 className="font-serif text-[clamp(32px,4vw,48px)] font-normal leading-tight mb-12">
            Meet the night crew
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {team.map((member) => (
              <div key={member.name} className="border border-[var(--border)] p-8 bg-[var(--card)]">
                <div className="w-16 h-16 bg-[var(--night)] rounded-full mb-6 flex items-center justify-center">
                  <span className="text-[var(--star)] text-2xl">
                    {member.name === 'The Bot' ? '' : member.name === 'Claude AI' ? '' : ''}
                  </span>
                </div>
                <h3 className="font-serif text-xl mb-1">{member.name}</h3>
                <p className="text-[11px] tracking-widest uppercase text-[var(--star)] mb-4">
                  {member.role}
                </p>
                <p className="text-[var(--muted)] text-sm font-light leading-relaxed">
                  {member.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 bg-[var(--ink)] text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="font-serif text-[clamp(32px,4vw,48px)] font-normal text-[#f5f2ec] leading-tight mb-6">
            Ready to sleep better?
          </h2>
          <p className="text-[rgba(245,242,236,0.5)] text-base font-light mb-10">
            Start your free trial tonight. No credit card required.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link href="/auth/signup" className="btn-primary">
              Start applying tonight
            </Link>
            <Link href="/contact" className="btn-ghost">
              Talk to us
            </Link>
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
