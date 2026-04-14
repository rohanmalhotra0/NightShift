'use client';

import { useState } from 'react';
import Link from 'next/link';

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    message: '',
  });
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');

    try {
      const res = await fetch('http://localhost:8000/contact/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to send message');
      }

      setStatus('success');
      setFormData({ name: '', email: '', subject: '', message: '' });
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--night)]">
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
            <Link href="/about" className="text-xs text-[rgba(245,242,236,0.4)] tracking-wide hover:text-[rgba(245,242,236,0.9)] transition-colors">
              About
            </Link>
          </li>
          <li>
            <Link href="/contact" className="text-xs text-[rgba(245,242,236,0.9)] tracking-wide">
              Contact
            </Link>
          </li>
        </ul>
        <Link href="/auth/signup" className="btn-primary text-xs py-2.5 px-6">
          Get started
        </Link>
      </nav>

      {/* Stars background */}
      <div className="stars fixed inset-0 pointer-events-none" />

      {/* Content */}
      <div className="relative z-10 pt-32 pb-20 px-6">
        <div className="max-w-2xl mx-auto">
          <p className="text-[11px] tracking-[0.15em] uppercase text-[var(--star)] mb-4">
            Contact Us
          </p>
          <h1 className="font-serif text-[clamp(36px,5vw,56px)] font-normal text-[#f5f2ec] leading-tight mb-6">
            Get in touch
          </h1>
          <p className="text-[rgba(245,242,236,0.5)] text-sm font-light mb-12 max-w-lg">
            Have questions about NightShift? Want to learn more about how we can help automate your job search? We'd love to hear from you.
          </p>

          {status === 'success' ? (
            <div className="bg-[rgba(200,185,122,0.1)] border border-[rgba(200,185,122,0.3)] p-8 text-center">
              <h2 className="font-serif text-2xl text-[#f5f2ec] mb-4">Message Sent</h2>
              <p className="text-[rgba(245,242,236,0.6)] text-sm mb-6">
                Thank you for reaching out. We'll get back to you within 24 hours.
              </p>
              <button
                onClick={() => setStatus('idle')}
                className="btn-ghost"
              >
                Send another message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors"
                    placeholder="Your name"
                  />
                </div>
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors"
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                  Subject
                </label>
                <input
                  type="text"
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors"
                  placeholder="What's this about?"
                />
              </div>

              <div>
                <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                  Message
                </label>
                <textarea
                  required
                  rows={6}
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors resize-none"
                  placeholder="Tell us how we can help..."
                />
              </div>

              {status === 'error' && (
                <p className="text-red-400 text-sm">{errorMessage}</p>
              )}

              <button
                type="submit"
                disabled={status === 'loading'}
                className="btn-primary w-full md:w-auto disabled:opacity-50"
              >
                {status === 'loading' ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          )}

          {/* Contact Info */}
          <div className="mt-20 pt-12 border-t border-[rgba(245,242,236,0.06)]">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <h3 className="font-serif text-lg text-[#f5f2ec] mb-2">Email</h3>
                <p className="text-[rgba(245,242,236,0.4)] text-sm font-light">
                  hello@nightshift.app
                </p>
              </div>
              <div>
                <h3 className="font-serif text-lg text-[#f5f2ec] mb-2">Response Time</h3>
                <p className="text-[rgba(245,242,236,0.4)] text-sm font-light">
                  Within 24 hours
                </p>
              </div>
              <div>
                <h3 className="font-serif text-lg text-[#f5f2ec] mb-2">Support</h3>
                <p className="text-[rgba(245,242,236,0.4)] text-sm font-light">
                  Pro & Max plans get priority
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 py-12 px-6 text-center border-t border-[rgba(245,242,236,0.06)]">
        <div className="font-serif text-2xl text-[#f5f2ec] italic mb-3">
          NightShift
        </div>
        <p className="text-xs text-[rgba(245,242,236,0.25)] font-light">
          We apply to jobs for you while you sleep.
        </p>
      </footer>
    </div>
  );
}
