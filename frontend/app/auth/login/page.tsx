'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/lib/auth';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setError('');
    setIsLoading(true);

    try {
      await login(data.email, data.password);
      router.push('/dashboard');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--night)] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Stars background */}
      <div className="stars" />

      {/* Moon */}
      <div className="absolute top-16 right-32 w-[72px] h-[72px] rounded-full bg-[#f0e8c8] shadow-[0_0_40px_rgba(240,232,200,0.3),0_0_80px_rgba(240,232,200,0.1)] animate-moonrise hidden lg:block" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-10">
          <Link href="/" className="font-serif text-3xl text-[#f5f2ec] italic">
            NightShift
          </Link>
        </div>

        {/* Card */}
        <div className="border border-[rgba(245,242,236,0.1)] bg-[rgba(13,15,20,0.8)] backdrop-blur-xl p-10">
          <div className="text-center mb-8">
            <h1 className="font-serif text-3xl text-[#f5f2ec] mb-2">Welcome back</h1>
            <p className="text-[rgba(245,242,236,0.4)] text-sm font-light">
              Sign in to continue your night shift
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                Email
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors placeholder:text-[rgba(245,242,236,0.2)]"
                {...register('email')}
              />
              {errors.email && (
                <p className="mt-1 text-red-400 text-xs">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                Password
              </label>
              <input
                type="password"
                placeholder="Enter your password"
                className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors placeholder:text-[rgba(245,242,236,0.2)]"
                {...register('password')}
              />
              {errors.password && (
                <p className="mt-1 text-red-400 text-xs">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full disabled:opacity-50"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-[rgba(245,242,236,0.4)]">
            Don&apos;t have an account?{' '}
            <Link href="/auth/signup" className="text-[var(--star)] hover:underline">
              Sign up
            </Link>
          </p>
        </div>

        {/* Back to home */}
        <p className="mt-6 text-center">
          <Link href="/" className="text-[rgba(245,242,236,0.3)] text-xs hover:text-[rgba(245,242,236,0.6)] transition-colors">
            Back to home
          </Link>
        </p>
      </div>
    </div>
  );
}
