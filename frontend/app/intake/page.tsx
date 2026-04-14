'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, Upload, X, Check } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { users } from '@/lib/api';

const JOB_TITLES = [
  'Software Engineer',
  'Backend Developer',
  'Frontend Developer',
  'Full Stack Developer',
  'Data Engineer',
  'DevOps Engineer',
  'Machine Learning Engineer',
  'Product Manager',
  'Data Scientist',
  'Mobile Developer',
];

const LOCATIONS = [
  'Remote',
  'San Francisco, CA',
  'New York, NY',
  'Seattle, WA',
  'Austin, TX',
  'Los Angeles, CA',
  'Boston, MA',
  'Denver, CO',
  'Chicago, IL',
  'Atlanta, GA',
];

const REMOTE_PREFS = [
  { value: 'remote', label: 'Remote only' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
  { value: 'any', label: 'Any' },
];

const WORK_AUTH_OPTIONS = [
  'US Citizen',
  'Green Card',
  'H1B Visa',
  'OPT/CPT',
  'Other Work Visa',
  'No Authorization Required',
];

type IntakeData = {
  jobTitles: string[];
  customTitle: string;
  locations: string[];
  customLocation: string;
  salaryMin: string;
  workAuth: string;
  remotePref: string;
  resumeFile: File | null;
  generateCoverLetter: boolean;
};

export default function IntakePage() {
  const router = useRouter();
  const { token } = useAuth();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [data, setData] = useState<IntakeData>({
    jobTitles: [],
    customTitle: '',
    locations: [],
    customLocation: '',
    salaryMin: '',
    workAuth: '',
    remotePref: 'any',
    resumeFile: null,
    generateCoverLetter: false,
  });

  const addCustomTitle = () => {
    const title = data.customTitle.trim();
    if (title && !data.jobTitles.includes(title)) {
      setData((prev) => ({ ...prev, jobTitles: [...prev.jobTitles, title], customTitle: '' }));
    }
  };

  const addCustomLocation = () => {
    const loc = data.customLocation.trim();
    if (loc && !data.locations.includes(loc)) {
      setData((prev) => ({ ...prev, locations: [...prev.locations, loc], customLocation: '' }));
    }
  };

  const totalSteps = 5;

  const toggleSelection = (field: 'jobTitles' | 'locations', value: string) => {
    setData((prev) => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter((v) => v !== value)
        : [...prev[field], value],
    }));
  };

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setData((prev) => ({ ...prev, resumeFile: file }));
    }
  }, []);

  const handleSubmit = async () => {
    if (!token) return;
    setIsSubmitting(true);
    try {
      const titles = data.customTitle
        ? [...data.jobTitles, data.customTitle]
        : data.jobTitles;

      await users.updatePrefs(token, {
        job_titles: titles,
        locations: data.locations,
        salary_min: data.salaryMin ? parseInt(data.salaryMin) : null,
        work_auth: data.workAuth,
        remote_pref: data.remotePref,
        generate_cover_letter: data.generateCoverLetter,
      });

      if (data.resumeFile) {
        const formData = new FormData();
        formData.append('file', data.resumeFile);
        formData.append('is_primary', 'true');
        await fetch('/api/users/resume', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
      }

      router.push('/dashboard');
    } catch (error) {
      console.error('Failed to save preferences:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1: return data.jobTitles.length > 0 || data.customTitle !== '';
      case 2: return data.locations.length > 0;
      case 3: return true;
      case 4: return data.workAuth !== '';
      case 5: return true;
      default: return false;
    }
  };

  const stepTitles = [
    'What job titles are you looking for?',
    'Where do you want to work?',
    'Salary & work preferences',
    'Work authorization',
    'Upload your resume',
  ];

  return (
    <div className="min-h-screen bg-[var(--night)] relative">
      {/* Stars */}
      <div className="stars fixed inset-0 pointer-events-none" />

      <div className="relative z-10 py-12 px-4">
        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="text-center mb-10">
            <div className="font-serif text-2xl text-[#f5f2ec] italic mb-6">NightShift</div>
            <h1 className="font-serif text-3xl text-[#f5f2ec] mb-2">Set up your preferences</h1>
            <p className="text-[rgba(245,242,236,0.4)] text-sm tracking-wide">
              Step {step} of {totalSteps}
            </p>
          </div>

          {/* Progress bar */}
          <div className="mb-8">
            <div className="h-px bg-[rgba(245,242,236,0.08)] relative">
              <div
                className="h-px bg-[var(--star)] transition-all duration-500 absolute top-0 left-0"
                style={{ width: `${(step / totalSteps) * 100}%` }}
              />
            </div>
          </div>

          {/* Card */}
          <div className="border border-[rgba(245,242,236,0.08)] bg-[rgba(245,242,236,0.02)] p-8">
            {/* Step title */}
            <h2 className="font-serif text-xl text-[#f5f2ec] mb-6">
              {stepTitles[step - 1]}
            </h2>

            {/* Step 1: Job Titles */}
            {step === 1 && (
              <div className="space-y-6">
                <div className="flex flex-wrap gap-2">
                  {JOB_TITLES.map((title) => (
                    <button
                      key={title}
                      onClick={() => toggleSelection('jobTitles', title)}
                      className={`px-4 py-2 text-sm font-light transition-all ${
                        data.jobTitles.includes(title)
                          ? 'bg-[var(--star)] text-[var(--night)] font-medium'
                          : 'border border-[rgba(245,242,236,0.15)] text-[rgba(245,242,236,0.6)] hover:border-[var(--star)] hover:text-[rgba(245,242,236,0.9)]'
                      }`}
                    >
                      {title}
                    </button>
                  ))}
                  {/* Custom titles added by user */}
                  {data.jobTitles.filter(t => !JOB_TITLES.includes(t)).map((title) => (
                    <button
                      key={title}
                      onClick={() => toggleSelection('jobTitles', title)}
                      className="px-4 py-2 text-sm font-medium transition-all bg-[var(--star)] text-[var(--night)] flex items-center gap-2"
                    >
                      {title}
                      <X className="h-3 w-3" />
                    </button>
                  ))}
                </div>
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                    Add a custom title — press Enter
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g., Cloud Engineer"
                      value={data.customTitle}
                      onChange={(e) => setData((prev) => ({ ...prev, customTitle: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomTitle(); } }}
                      className="flex-1 bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light placeholder-[rgba(245,242,236,0.25)] focus:border-[var(--star)] focus:outline-none transition-colors"
                    />
                    <button
                      onClick={addCustomTitle}
                      disabled={!data.customTitle.trim()}
                      className="px-4 py-3 bg-[var(--star)] text-[var(--night)] text-sm font-medium disabled:opacity-30 transition-opacity"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Locations */}
            {step === 2 && (
              <div className="space-y-6">
                <div className="flex flex-wrap gap-2">
                  {LOCATIONS.map((location) => (
                    <button
                      key={location}
                      onClick={() => toggleSelection('locations', location)}
                      className={`px-4 py-2 text-sm font-light transition-all ${
                        data.locations.includes(location)
                          ? 'bg-[var(--star)] text-[var(--night)] font-medium'
                          : 'border border-[rgba(245,242,236,0.15)] text-[rgba(245,242,236,0.6)] hover:border-[var(--star)] hover:text-[rgba(245,242,236,0.9)]'
                      }`}
                    >
                      {location}
                    </button>
                  ))}
                  {/* Custom locations added by user */}
                  {data.locations.filter(l => !LOCATIONS.includes(l)).map((loc) => (
                    <button
                      key={loc}
                      onClick={() => toggleSelection('locations', loc)}
                      className="px-4 py-2 text-sm font-medium transition-all bg-[var(--star)] text-[var(--night)] flex items-center gap-2"
                    >
                      {loc}
                      <X className="h-3 w-3" />
                    </button>
                  ))}
                </div>
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                    Add any city, state, or country — press Enter
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g., London, UK or Toronto, Canada"
                      value={data.customLocation}
                      onChange={(e) => setData((prev) => ({ ...prev, customLocation: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomLocation(); } }}
                      className="flex-1 bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light placeholder-[rgba(245,242,236,0.25)] focus:border-[var(--star)] focus:outline-none transition-colors"
                    />
                    <button
                      onClick={addCustomLocation}
                      disabled={!data.customLocation.trim()}
                      className="px-4 py-3 bg-[var(--star)] text-[var(--night)] text-sm font-medium disabled:opacity-30 transition-opacity"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Salary & Remote */}
            {step === 3 && (
              <div className="space-y-8">
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-2">
                    Minimum salary (optional)
                  </label>
                  <input
                    type="number"
                    placeholder="e.g., 100000"
                    value={data.salaryMin}
                    onChange={(e) => setData((prev) => ({ ...prev, salaryMin: e.target.value }))}
                    className="w-full bg-transparent border border-[rgba(245,242,236,0.1)] px-4 py-3 text-[#f5f2ec] text-sm font-light placeholder-[rgba(245,242,236,0.25)] focus:border-[var(--star)] focus:outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-[11px] tracking-widest uppercase text-[rgba(245,242,236,0.4)] mb-3">
                    Remote preference
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {REMOTE_PREFS.map((pref) => (
                      <button
                        key={pref.value}
                        onClick={() => setData((prev) => ({ ...prev, remotePref: pref.value }))}
                        className={`px-4 py-3 text-sm font-light transition-all ${
                          data.remotePref === pref.value
                            ? 'bg-[var(--star)] text-[var(--night)] font-medium'
                            : 'border border-[rgba(245,242,236,0.15)] text-[rgba(245,242,236,0.6)] hover:border-[var(--star)] hover:text-[rgba(245,242,236,0.9)]'
                        }`}
                      >
                        {pref.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Step 4: Work Authorization */}
            {step === 4 && (
              <div className="space-y-2">
                {WORK_AUTH_OPTIONS.map((option) => (
                  <button
                    key={option}
                    onClick={() => setData((prev) => ({ ...prev, workAuth: option }))}
                    className={`w-full px-4 py-3 text-left text-sm font-light transition-all flex items-center justify-between ${
                      data.workAuth === option
                        ? 'bg-[var(--star)] text-[var(--night)] font-medium'
                        : 'border border-[rgba(245,242,236,0.1)] text-[rgba(245,242,236,0.6)] hover:border-[var(--star)] hover:text-[rgba(245,242,236,0.9)]'
                    }`}
                  >
                    {option}
                    {data.workAuth === option && <Check className="h-4 w-4" />}
                  </button>
                ))}
              </div>
            )}

            {/* Step 5: Resume Upload */}
            {step === 5 && (
              <div className="space-y-6">
                <div
                  className={`border border-dashed p-10 text-center transition-colors ${
                    data.resumeFile
                      ? 'border-[var(--star)] bg-[rgba(200,185,122,0.05)]'
                      : 'border-[rgba(245,242,236,0.15)] hover:border-[rgba(245,242,236,0.3)]'
                  }`}
                >
                  {data.resumeFile ? (
                    <div className="flex items-center justify-center gap-3">
                      <span className="text-sm text-[rgba(245,242,236,0.8)]">{data.resumeFile.name}</span>
                      <button
                        onClick={() => setData((prev) => ({ ...prev, resumeFile: null }))}
                        className="text-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ) : (
                    <label className="cursor-pointer block">
                      <Upload className="h-8 w-8 text-[rgba(245,242,236,0.25)] mx-auto mb-3" />
                      <p className="text-sm text-[rgba(245,242,236,0.5)]">
                        <span className="text-[var(--star)]">Click to upload</span> or drag and drop
                      </p>
                      <p className="text-xs text-[rgba(245,242,236,0.25)] mt-2">PDF or Word · max 10MB</p>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        className="hidden"
                        onChange={handleFileChange}
                      />
                    </label>
                  )}
                </div>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <div
                    onClick={() =>
                      setData((prev) => ({ ...prev, generateCoverLetter: !prev.generateCoverLetter }))
                    }
                    className={`w-5 h-5 border flex items-center justify-center transition-colors cursor-pointer ${
                      data.generateCoverLetter
                        ? 'bg-[var(--star)] border-[var(--star)]'
                        : 'border-[rgba(245,242,236,0.2)] hover:border-[var(--star)]'
                    }`}
                  >
                    {data.generateCoverLetter && <Check className="h-3 w-3 text-[var(--night)]" />}
                  </div>
                  <span className="text-sm text-[rgba(245,242,236,0.6)] font-light group-hover:text-[rgba(245,242,236,0.9)] transition-colors">
                    Generate AI cover letters for each application
                  </span>
                </label>
              </div>
            )}
          </div>

          {/* Navigation */}
          <div className="flex justify-between mt-6">
            <button
              onClick={() => setStep((s) => s - 1)}
              disabled={step === 1}
              className="flex items-center gap-2 px-6 py-3 text-sm border border-[rgba(245,242,236,0.15)] text-[rgba(245,242,236,0.5)] hover:border-[rgba(245,242,236,0.4)] hover:text-[rgba(245,242,236,0.9)] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>

            {step < totalSteps ? (
              <button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canProceed()}
                className="flex items-center gap-2 btn-primary disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
                <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? 'Saving...' : 'Complete Setup'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
