import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User } from '@/types/api';

interface TimezoneContextType {
  timezone: string;
  locale: string;
  setUserTimezone: (timezone: string, locale?: string) => void;
  detectSystemTimezone: () => string;
  getTimezoneOffset: () => string;
}

const TimezoneContext = createContext<TimezoneContextType | undefined>(undefined);

interface TimezoneProviderProps {
  children: ReactNode;
  user?: User | null;
}

export function TimezoneProvider({ children, user }: TimezoneProviderProps) {
  const [timezone, setTimezone] = useState<string>('America/New_York'); // Default to Eastern
  const [locale, setLocale] = useState<string>('en-US');

  const detectSystemTimezone = (): string => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return 'America/New_York'; // Fallback to Eastern
    }
  };

  const getTimezoneOffset = (): string => {
    try {
      const now = new Date();
      const formatter = new Intl.DateTimeFormat('en', {
        timeZone: timezone,
        timeZoneName: 'short'
      });
      const parts = formatter.formatToParts(now);
      const timeZoneName = parts.find(part => part.type === 'timeZoneName')?.value;
      return timeZoneName || '';
    } catch {
      return '';
    }
  };

  const setUserTimezone = (newTimezone: string, newLocale?: string) => {
    setTimezone(newTimezone);
    if (newLocale) {
      setLocale(newLocale);
    }
    // Store in localStorage as backup
    localStorage.setItem('userTimezone', newTimezone);
    if (newLocale) {
      localStorage.setItem('userLocale', newLocale);
    }
  };

  // Initialize timezone from user preferences or localStorage/system
  useEffect(() => {
    let initialTimezone = 'America/New_York'; // Default to Eastern
    let initialLocale = 'en-US';

    // Priority order: user preference > localStorage > system detection
    if (user?.timezone) {
      initialTimezone = user.timezone;
      initialLocale = user.locale || 'en-US';
    } else {
      const savedTimezone = localStorage.getItem('userTimezone');
      const savedLocale = localStorage.getItem('userLocale');

      if (savedTimezone) {
        initialTimezone = savedTimezone;
        initialLocale = savedLocale || 'en-US';
      } else {
        // Only use system detection as last resort
        const systemTimezone = detectSystemTimezone();
        if (systemTimezone && systemTimezone !== 'UTC') {
          initialTimezone = systemTimezone;
        }
      }
    }

    setTimezone(initialTimezone);
    setLocale(initialLocale);
  }, [user]);

  const value: TimezoneContextType = {
    timezone,
    locale,
    setUserTimezone,
    detectSystemTimezone,
    getTimezoneOffset
  };

  return (
    <TimezoneContext.Provider value={value}>
      {children}
    </TimezoneContext.Provider>
  );
}

export function useTimezone(): TimezoneContextType {
  const context = useContext(TimezoneContext);
  if (context === undefined) {
    throw new Error('useTimezone must be used within a TimezoneProvider');
  }
  return context;
}

// Common US timezones for user selection
export const COMMON_TIMEZONES = [
  { value: 'America/New_York', label: 'Eastern Time (ET)', group: 'US' },
  { value: 'America/Chicago', label: 'Central Time (CT)', group: 'US' },
  { value: 'America/Denver', label: 'Mountain Time (MT)', group: 'US' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)', group: 'US' },
  { value: 'America/Anchorage', label: 'Alaska Time (AKT)', group: 'US' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (HST)', group: 'US' },
  { value: 'UTC', label: 'UTC (Coordinated Universal Time)', group: 'International' },
  { value: 'Europe/London', label: 'London (GMT/BST)', group: 'International' },
  { value: 'Europe/Paris', label: 'Central European Time (CET)', group: 'International' },
  { value: 'Asia/Tokyo', label: 'Japan Standard Time (JST)', group: 'International' },
] as const;
