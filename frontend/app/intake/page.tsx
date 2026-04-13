'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Moon, ArrowLeft, ArrowRight, Upload, X, Check } from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
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
    salaryMin: '',
    workAuth: '',
    remotePref: 'any',
    resumeFile: null,
    generateCoverLetter: false,
  });

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
      // Update preferences
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

      // Upload resume if provided
      if (data.resumeFile) {
        const formData = new FormData();
        formData.append('file', data.resumeFile);
        formData.append('is_primary', 'true');

        await fetch('/api/users/resume', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
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
      case 1:
        return data.jobTitles.length > 0 || data.customTitle;
      case 2:
        return data.locations.length > 0;
      case 3:
        return true; // Salary is optional
      case 4:
        return data.workAuth !== '';
      case 5:
        return true; // Resume is optional
      default:
        return false;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center space-x-2 mb-4">
            <Moon className="h-8 w-8 text-primary-600" />
            <span className="text-xl font-bold text-gray-900">NightShift</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Set up your preferences</h1>
          <p className="text-gray-500 mt-1">Step {step} of {totalSteps}</p>
        </div>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="h-2 bg-gray-200 rounded-full">
            <div
              className="h-2 bg-primary-600 rounded-full transition-all"
              style={{ width: `${(step / totalSteps) * 100}%` }}
            />
          </div>
        </div>

        {/* Step content */}
        <Card>
          <CardHeader>
            <CardTitle>
              {step === 1 && 'What job titles are you looking for?'}
              {step === 2 && 'Where do you want to work?'}
              {step === 3 && 'Salary & work preferences'}
              {step === 4 && 'Work authorization'}
              {step === 5 && 'Upload your resume'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Step 1: Job Titles */}
            {step === 1 && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {JOB_TITLES.map((title) => (
                    <button
                      key={title}
                      onClick={() => toggleSelection('jobTitles', title)}
                      className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                        data.jobTitles.includes(title)
                          ? 'bg-primary-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {title}
                    </button>
                  ))}
                </div>
                <Input
                  label="Or add a custom title"
                  placeholder="e.g., Cloud Engineer"
                  value={data.customTitle}
                  onChange={(e) => setData((prev) => ({ ...prev, customTitle: e.target.value }))}
                />
              </div>
            )}

            {/* Step 2: Locations */}
            {step === 2 && (
              <div className="flex flex-wrap gap-2">
                {LOCATIONS.map((location) => (
                  <button
                    key={location}
                    onClick={() => toggleSelection('locations', location)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                      data.locations.includes(location)
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {location}
                  </button>
                ))}
              </div>
            )}

            {/* Step 3: Salary & Remote */}
            {step === 3 && (
              <div className="space-y-6">
                <Input
                  label="Minimum salary (optional)"
                  type="number"
                  placeholder="e.g., 100000"
                  value={data.salaryMin}
                  onChange={(e) => setData((prev) => ({ ...prev, salaryMin: e.target.value }))}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Remote preference
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {REMOTE_PREFS.map((pref) => (
                      <button
                        key={pref.value}
                        onClick={() => setData((prev) => ({ ...prev, remotePref: pref.value }))}
                        className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors border ${
                          data.remotePref === pref.value
                            ? 'border-primary-600 bg-primary-50 text-primary-700'
                            : 'border-gray-200 text-gray-700 hover:bg-gray-50'
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
                    className={`w-full px-4 py-3 rounded-lg text-left text-sm font-medium transition-colors border flex items-center justify-between ${
                      data.workAuth === option
                        ? 'border-primary-600 bg-primary-50 text-primary-700'
                        : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {option}
                    {data.workAuth === option && <Check className="h-5 w-5" />}
                  </button>
                ))}
              </div>
            )}

            {/* Step 5: Resume Upload */}
            {step === 5 && (
              <div className="space-y-6">
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center ${
                    data.resumeFile ? 'border-primary-300 bg-primary-50' : 'border-gray-300'
                  }`}
                >
                  {data.resumeFile ? (
                    <div className="flex items-center justify-center space-x-2">
                      <span className="text-sm text-gray-700">{data.resumeFile.name}</span>
                      <button
                        onClick={() => setData((prev) => ({ ...prev, resumeFile: null }))}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <X className="h-5 w-5" />
                      </button>
                    </div>
                  ) : (
                    <label className="cursor-pointer">
                      <Upload className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                      <p className="text-sm text-gray-600">
                        <span className="text-primary-600 font-medium">Click to upload</span> or drag and drop
                      </p>
                      <p className="text-xs text-gray-400 mt-1">PDF or Word (max 10MB)</p>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        className="hidden"
                        onChange={handleFileChange}
                      />
                    </label>
                  )}
                </div>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={data.generateCoverLetter}
                    onChange={(e) =>
                      setData((prev) => ({ ...prev, generateCoverLetter: e.target.checked }))
                    }
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-700">
                    Generate cover letters with AI for each application
                  </span>
                </label>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between mt-6">
          <Button
            variant="outline"
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 1}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>

          {step < totalSteps ? (
            <Button onClick={() => setStep((s) => s + 1)} disabled={!canProceed()}>
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} isLoading={isSubmitting} disabled={!canProceed()}>
              Complete Setup
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
