'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/lib/auth';

const signupSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
});

type SignupForm = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupForm>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = async (data: SignupForm) => {
    setError('');
    setIsLoading(true);

    try {
      await signup(data.email, data.password);
      router.push('/intake');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Signup failed';
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
      <div className="absolute top-16 left-32 w-[72px] h-[72px] rounded-full bg-[#f0e8c8] shadow-[0_0_40px_rgba(240,232,200,0.3),0_0_80px_rgba(240,232,200,0.1)] animate-moonrise hidden lg:block" />

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
            <h1 className="font-serif text-3xl text-[#f5f2ec] mb-2">Start your night shift</h1>
            <p className="text-[rgba(245,242,236,0.4)] text-sm font-light">
              Create an account to automate your job search
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
                placeholder="Create a password"
                className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors placeholder:text-[rgba(245,242,236,0.2)]"
                {...register('password')}
              />
              {errors.password && (
                <p className="mt-1 text-red-400 text-xs">{errors.password.message}</p>
              )}
            </div>

            <div>
              <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                Confirm Password
              </label>
              <input
                type="password"
                placeholder="Confirm your password"
                className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light focus:border-[var(--star)] focus:outline-none transition-colors placeholder:text-[rgba(245,242,236,0.2)]"
                {...register('confirmPassword')}
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-red-400 text-xs">{errors.confirmPassword.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full disabled:opacity-50"
            >
              {isLoading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-[rgba(245,242,236,0.4)]">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-[var(--star)] hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        {/* Features */}
        <div className="mt-10 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-[var(--star)] text-xl mb-1"></div>
            <p className="text-[rgba(245,242,236,0.4)] text-[10px] tracking-wide uppercase">AI-Powered</p>
          </div>
          <div>
            <div className="text-[var(--star)] text-xl mb-1"></div>
            <p className="text-[rgba(245,242,236,0.4)] text-[10px] tracking-wide uppercase">While You Sleep</p>
          </div>
          <div>
            <div className="text-[var(--star)] text-xl mb-1"></div>
            <p className="text-[rgba(245,242,236,0.4)] text-[10px] tracking-wide uppercase">Full Tracking</p>
          </div>
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
