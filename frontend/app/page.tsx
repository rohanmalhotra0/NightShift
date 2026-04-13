'use client';

import Link from 'next/link';
import { Button } from '@/components/Button';
import { Card, CardContent } from '@/components/Card';
import { Moon, Zap, Shield, BarChart3, Check } from 'lucide-react';

const features = [
  {
    icon: Moon,
    title: 'Apply While You Sleep',
    description: 'Our bot runs nightly, submitting applications to jobs matching your preferences.',
  },
  {
    icon: Zap,
    title: 'AI-Powered Auto-Fill',
    description: 'Claude AI intelligently fills out application forms using your resume and preferences.',
  },
  {
    icon: Shield,
    title: 'CAPTCHA Solving',
    description: 'Built-in CAPTCHA solving ensures applications go through without interruption.',
  },
  {
    icon: BarChart3,
    title: 'Track Everything',
    description: 'Google Sheets integration logs every application with full details.',
  },
];

const tiers = [
  {
    name: 'Starter',
    price: 19,
    apps: 3,
    features: ['3 applications per night', 'LinkedIn & Indeed', 'Basic auto-fill', 'Google Sheets logging'],
  },
  {
    name: 'Pro',
    price: 39,
    apps: 10,
    features: ['10 applications per night', 'All job boards', 'Advanced auto-fill', 'Custom resume selection', 'Priority support'],
    popular: true,
  },
  {
    name: 'Max',
    price: 69,
    apps: 25,
    features: ['25 applications per night', 'All job boards', 'AI cover letters', 'Custom scheduling', 'Dedicated support'],
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Moon className="h-8 w-8 text-primary-600" />
            <span className="text-xl font-bold text-gray-900">NightShift</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link href="/auth/login">
              <Button variant="ghost">Log in</Button>
            </Link>
            <Link href="/auth/signup">
              <Button>Get Started</Button>
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl">
          We apply to jobs
          <br />
          <span className="text-primary-600">while you sleep</span>
        </h1>
        <p className="mt-6 text-lg text-gray-600 max-w-2xl mx-auto">
          Stop spending hours filling out the same forms. NightShift automatically applies to jobs matching your preferences every night using AI.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link href="/auth/signup">
            <Button size="lg">Start Free Trial</Button>
          </Link>
          <Link href="#pricing">
            <Button variant="outline" size="lg">View Pricing</Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
          How it works
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((feature) => (
            <Card key={feature.title} className="text-center p-6">
              <CardContent className="p-0">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-primary-100 text-primary-600 mb-4">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600 text-sm">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="container mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-4">
          Simple pricing
        </h2>
        <p className="text-center text-gray-600 mb-12">
          Choose the plan that fits your job search intensity
        </p>
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {tiers.map((tier) => (
            <Card
              key={tier.name}
              className={`relative ${tier.popular ? 'border-primary-500 border-2' : ''}`}
            >
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-primary-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                    Most Popular
                  </span>
                </div>
              )}
              <CardContent className="p-6">
                <h3 className="text-xl font-semibold text-gray-900">{tier.name}</h3>
                <div className="mt-4">
                  <span className="text-4xl font-bold text-gray-900">${tier.price}</span>
                  <span className="text-gray-500">/month</span>
                </div>
                <p className="mt-2 text-sm text-gray-600">
                  {tier.apps} applications per night
                </p>
                <ul className="mt-6 space-y-3">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex items-center text-sm text-gray-600">
                      <Check className="h-4 w-4 text-primary-600 mr-2 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link href="/auth/signup" className="block mt-8">
                  <Button
                    variant={tier.popular ? 'primary' : 'outline'}
                    className="w-full"
                  >
                    Get started
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-12">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <p>NightShift - Automated job applications powered by AI</p>
        </div>
      </footer>
    </div>
  );
}
