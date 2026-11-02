import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { TimezoneProvider, useTimezone, COMMON_TIMEZONES } from './TimezoneContext';
import type { User } from '@/types/api';

// Create mock storage that tracks calls but behaves dynamically
const storageMap = new Map<string, string>();
const mockLocalStorage = {
  getItem: vi.fn((key: string) => storageMap.get(key) || null),
  setItem: vi.fn((key: string, value: string) => storageMap.set(key, value)),
  removeItem: vi.fn((key: string) => storageMap.delete(key)),
  clear: vi.fn(() => storageMap.clear())
};

Object.defineProperty(global, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

// Mock Intl.DateTimeFormat for system timezone detection
const mockIntlDateTimeFormat = vi.fn();
global.Intl = {
  ...global.Intl,
  DateTimeFormat: mockIntlDateTimeFormat as any
};

// Test component that uses the timezone context
const TestComponent = () => {
  const {
    timezone,
    locale,
    setUserTimezone,
    detectSystemTimezone,
    getTimezoneOffset
  } = useTimezone();

  const handleSetTimezone = () => {
    // Use a random timezone from the common list
    const timezones = Object.keys(COMMON_TIMEZONES);
    const randomTz = timezones[Math.floor(Math.random() * timezones.length)];
    const locales = ['en-US', 'es-ES', 'fr-FR', 'de-DE', 'ja-JP'];
    const randomLocale = locales[Math.floor(Math.random() * locales.length)];
    setUserTimezone(randomTz, randomLocale);
  };

  const handleDetectSystem = () => {
    const systemTz = detectSystemTimezone();
    const systemElement = document.createElement('div');
    systemElement.setAttribute('data-testid', 'system-timezone');
    systemElement.textContent = systemTz;
    document.body.appendChild(systemElement);
  };

  const handleGetOffset = () => {
    const offset = getTimezoneOffset();
    const offsetElement = document.createElement('div');
    offsetElement.setAttribute('data-testid', 'timezone-offset');
    offsetElement.textContent = offset;
    document.body.appendChild(offsetElement);
  };

  return (
    <div>
      <div data-testid="current-timezone">{timezone}</div>
      <div data-testid="current-locale">{locale}</div>
      <button onClick={handleSetTimezone} data-testid="set-timezone">
        Set Timezone
      </button>
      <button onClick={handleDetectSystem} data-testid="detect-system">
        Detect System
      </button>
      <button onClick={handleGetOffset} data-testid="get-offset">
        Get Offset
      </button>
    </div>
  );
};

// Test component for error handling
const TestComponentWithoutProvider = () => {
  const context = useTimezone();
  return <div>{context ? 'has context' : 'no context'}</div>;
};

describe('TimezoneContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clean up any elements added to body during tests
    document.querySelectorAll('[data-testid="system-timezone"]').forEach(el => el.remove());
    document.querySelectorAll('[data-testid="timezone-offset"]').forEach(el => el.remove());

    // Clear storage
    storageMap.clear();

    // Reset Intl mock to return dynamic timezone
    const systemTimezones = ['America/Chicago', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney'];
    const randomSystemTz = systemTimezones[Math.floor(Math.random() * systemTimezones.length)];
    mockIntlDateTimeFormat.mockReturnValue({
      resolvedOptions: () => ({ timeZone: randomSystemTz }),
      formatToParts: () => [
        { type: 'timeZoneName', value: 'TZ' }
      ]
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('provides timezone context to children', () => {
    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    // Should have a timezone and locale set
    const timezoneElement = screen.getByTestId('current-timezone');
    const localeElement = screen.getByTestId('current-locale');

    expect(timezoneElement.textContent).toBeTruthy();
    expect(localeElement.textContent).toBeTruthy();
    // Timezone should be a valid format
    expect(timezoneElement.textContent).toMatch(/^[A-Za-z]+\/[A-Za-z_]+$/);
  });

  it('throws error when useTimezone is used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponentWithoutProvider />);
    }).toThrow('useTimezone must be used within a TimezoneProvider');

    consoleSpy.mockRestore();
  });

  it('initializes with user preference from props', () => {
    // Generate dynamic user with timezone preferences
    const timezones = Object.keys(COMMON_TIMEZONES);
    const userTimezone = timezones[Math.floor(Math.random() * timezones.length)];
    const userLocale = ['en-US', 'es-ES', 'fr-FR'][Math.floor(Math.random() * 3)];

    const mockUser: User = {
      id: Math.floor(Math.random() * 10000),
      first_name: `User${Math.floor(Math.random() * 100)}`,
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      username: `user${Math.floor(Math.random() * 100)}`,
      role: 'user',
      timezone: userTimezone,
      locale: userLocale,
      created_at: new Date().toISOString(),
      last_login_at: new Date().toISOString()
    };

    render(
      <TimezoneProvider user={mockUser}>
        <TestComponent />
      </TimezoneProvider>
    );

    expect(screen.getByTestId('current-timezone')).toHaveTextContent(userTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent(userLocale);
  });

  it('falls back to localStorage when no user preference', () => {
    // Set dynamic values in storage
    const storedTimezone = ['America/Denver', 'Europe/Paris', 'Asia/Shanghai'][Math.floor(Math.random() * 3)];
    const storedLocale = ['fr-FR', 'de-DE', 'it-IT'][Math.floor(Math.random() * 3)];

    storageMap.set('userTimezone', storedTimezone);
    storageMap.set('userLocale', storedLocale);

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    expect(mockLocalStorage.getItem).toHaveBeenCalledWith('userTimezone');
    expect(mockLocalStorage.getItem).toHaveBeenCalledWith('userLocale');
    expect(screen.getByTestId('current-timezone')).toHaveTextContent(storedTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent(storedLocale);
  });

  it('falls back to system detection when no user or localStorage preference', () => {
    const systemTz = ['Europe/London', 'America/Toronto', 'Pacific/Auckland'][Math.floor(Math.random() * 3)];
    mockIntlDateTimeFormat.mockReturnValue({
      resolvedOptions: () => ({ timeZone: systemTz })
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    const timezoneElement = screen.getByTestId('current-timezone');
    // Should use the system timezone or a fallback
    expect(timezoneElement.textContent).toBeTruthy();
    // If system detection worked, it should use that timezone
    if (systemTz !== 'UTC') {
      expect(timezoneElement.textContent).toBe(systemTz);
    }
  });

  it('handles UTC system detection appropriately', () => {
    mockIntlDateTimeFormat.mockReturnValue({
      resolvedOptions: () => ({ timeZone: 'UTC' })
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    const timezoneElement = screen.getByTestId('current-timezone');
    // Should have a timezone set (either UTC or a fallback)
    expect(timezoneElement.textContent).toBeTruthy();
    // Should be a valid timezone format
    expect(timezoneElement.textContent).toMatch(/^[A-Za-z]+(\/[A-Za-z_]+)?$/);
  });

  it('handles system detection errors gracefully', () => {
    mockIntlDateTimeFormat.mockImplementation(() => {
      throw new Error('Intl not supported');
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    // Should fall back to default
    expect(screen.getByTestId('current-timezone')).toHaveTextContent('America/New_York');
  });

  it('sets user timezone and saves to localStorage', () => {
    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    const initialTimezone = screen.getByTestId('current-timezone').textContent;
    const _initialLocale = screen.getByTestId('current-locale').textContent;

    fireEvent.click(screen.getByTestId('set-timezone'));

    const newTimezone = screen.getByTestId('current-timezone').textContent;
    const newLocale = screen.getByTestId('current-locale').textContent;

    // Verify that timezone changed and is a valid format
    expect(newTimezone).not.toBe(initialTimezone);
    expect(newTimezone).toMatch(/^[A-Za-z_]+\/[A-Za-z_]+$/);
    expect(newLocale).toMatch(/^[a-z]{2}-[A-Z]{2}$/);

    // Verify storage was called with the new values
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('userTimezone', newTimezone);
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('userLocale', newLocale);
  });

  it('sets timezone without changing locale when locale not provided', () => {
    const TimezoneOnlyComponent = () => {
      const { setUserTimezone } = useTimezone();

      const handleSetTimezoneOnly = () => {
        setUserTimezone('Europe/Paris');
      };

      return (
        <button onClick={handleSetTimezoneOnly} data-testid="set-timezone-only">
          Set Timezone Only
        </button>
      );
    };

    render(
      <TimezoneProvider>
        <TimezoneOnlyComponent />
        <TestComponent />
      </TimezoneProvider>
    );

    const originalLocale = screen.getByTestId('current-locale').textContent;

    fireEvent.click(screen.getByTestId('set-timezone-only'));

    expect(screen.getByTestId('current-timezone')).toHaveTextContent('Europe/Paris');
    expect(screen.getByTestId('current-locale')).toHaveTextContent(originalLocale || '');

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('userTimezone', 'Europe/Paris');
    expect(mockLocalStorage.setItem).not.toHaveBeenCalledWith('userLocale', expect.anything());
  });

  it('detects system timezone correctly', () => {
    mockIntlDateTimeFormat.mockReturnValue({
      resolvedOptions: () => ({ timeZone: 'Asia/Tokyo' })
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('detect-system'));

    expect(screen.getByTestId('system-timezone')).toHaveTextContent('Asia/Tokyo');
  });

  it('handles system timezone detection errors', () => {
    mockIntlDateTimeFormat.mockImplementation(() => {
      throw new Error('Detection failed');
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('detect-system'));

    expect(screen.getByTestId('system-timezone')).toHaveTextContent('America/New_York');
  });

  it('gets timezone offset correctly', () => {
    mockIntlDateTimeFormat.mockReturnValue({
      formatToParts: vi.fn().mockReturnValue([
        { type: 'month', value: '1' },
        { type: 'day', value: '15' },
        { type: 'year', value: '2024' },
        { type: 'timeZoneName', value: 'PST' }
      ])
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('get-offset'));

    expect(screen.getByTestId('timezone-offset')).toHaveTextContent('PST');
  });

  it('handles timezone offset errors gracefully', () => {
    mockIntlDateTimeFormat.mockReturnValue({
      formatToParts: vi.fn().mockImplementation(() => {
        throw new Error('Format error');
      })
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('get-offset'));

    expect(screen.getByTestId('timezone-offset')).toHaveTextContent('');
  });

  it('handles missing timeZoneName in format parts', () => {
    mockIntlDateTimeFormat.mockReturnValue({
      formatToParts: vi.fn().mockReturnValue([
        { type: 'month', value: '1' },
        { type: 'day', value: '15' },
        { type: 'year', value: '2024' }
        // No timeZoneName part
      ])
    });

    render(
      <TimezoneProvider>
        <TestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('get-offset'));

    expect(screen.getByTestId('timezone-offset')).toHaveTextContent('');
  });

  it('updates when user prop changes', () => {
    // Generate dynamic user data
    const timezones = Object.keys(COMMON_TIMEZONES);
    const locales = ['en-US', 'fr-FR', 'de-DE', 'es-ES', 'ja-JP'];

    const initialTimezone = timezones[Math.floor(Math.random() * timezones.length)];
    const initialLocale = locales[Math.floor(Math.random() * locales.length)];

    const initialUser: User = {
      id: Math.floor(Math.random() * 10000),
      first_name: `User${Math.floor(Math.random() * 100)}`,
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      username: `user${Math.floor(Math.random() * 100)}`,
      role: 'user',
      timezone: initialTimezone,
      locale: initialLocale,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    const { rerender } = render(
      <TimezoneProvider user={initialUser}>
        <TestComponent />
      </TimezoneProvider>
    );

    expect(screen.getByTestId('current-timezone')).toHaveTextContent(initialTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent(initialLocale);

    // Change to different timezone and locale
    const updatedTimezone = timezones.find(tz => tz !== initialTimezone) || 'UTC';
    const updatedLocale = locales.find(loc => loc !== initialLocale) || 'en-US';

    const updatedUser: User = {
      ...initialUser,
      timezone: updatedTimezone,
      locale: updatedLocale
    };

    rerender(
      <TimezoneProvider user={updatedUser}>
        <TestComponent />
      </TimezoneProvider>
    );

    expect(screen.getByTestId('current-timezone')).toHaveTextContent(updatedTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent(updatedLocale);
  });

  it('prioritizes user preference over localStorage', () => {
    // Generate dynamic storage values
    const storageTimezone = ['America/Denver', 'Europe/Berlin', 'Australia/Sydney'][Math.floor(Math.random() * 3)];
    const storageLocale = ['es-ES', 'fr-FR', 'it-IT'][Math.floor(Math.random() * 3)];

    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'userTimezone') return storageTimezone;
      if (key === 'userLocale') return storageLocale;
      return null;
    });

    // Generate different user preferences
    const userTimezone = ['Asia/Tokyo', 'Europe/London', 'America/New_York'][Math.floor(Math.random() * 3)];
    const userLocale = ['ja-JP', 'en-GB', 'en-US'][Math.floor(Math.random() * 3)];

    const mockUser: User = {
      id: Math.floor(Math.random() * 10000),
      first_name: `User${Math.floor(Math.random() * 100)}`,
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      username: `user${Math.floor(Math.random() * 100)}`,
      role: 'user',
      timezone: userTimezone,
      locale: userLocale,
      created_at: new Date().toISOString(),
      last_login_at: new Date().toISOString()
    };

    render(
      <TimezoneProvider user={mockUser}>
        <TestComponent />
      </TimezoneProvider>
    );

    // Should use user preference, not localStorage
    expect(screen.getByTestId('current-timezone')).toHaveTextContent(userTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent(userLocale);
    // Verify it's different from storage values (if they differ)
    if (userTimezone !== storageTimezone) {
      expect(screen.getByTestId('current-timezone')).not.toHaveTextContent(storageTimezone);
    }
    if (userLocale !== storageLocale) {
      expect(screen.getByTestId('current-locale')).not.toHaveTextContent(storageLocale);
    }
  });

  it('handles user without timezone/locale properties', () => {
    // Generate dynamic storage value
    const storageTimezone = ['America/Denver', 'Europe/Paris', 'Asia/Shanghai'][Math.floor(Math.random() * 3)];

    const userWithoutTimezone: User = {
      id: Math.floor(Math.random() * 10000),
      first_name: `User${Math.floor(Math.random() * 100)}`,
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      username: `user${Math.floor(Math.random() * 100)}`,
      role: 'user',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'userTimezone') return storageTimezone;
      return null;
    });

    render(
      <TimezoneProvider user={userWithoutTimezone}>
        <TestComponent />
      </TimezoneProvider>
    );

    // Should fall back to localStorage
    expect(screen.getByTestId('current-timezone')).toHaveTextContent(storageTimezone);
    expect(screen.getByTestId('current-locale')).toHaveTextContent('en-US'); // Default locale when not in storage
  });

  it('saves locale to localStorage when provided', () => {
    const LocaleTestComponent = () => {
      const { setUserTimezone } = useTimezone();

      const handleSetWithLocale = () => {
        setUserTimezone('Europe/Berlin', 'de-DE');
      };

      return (
        <button onClick={handleSetWithLocale} data-testid="set-with-locale">
          Set With Locale
        </button>
      );
    };

    render(
      <TimezoneProvider>
        <LocaleTestComponent />
      </TimezoneProvider>
    );

    fireEvent.click(screen.getByTestId('set-with-locale'));

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('userTimezone', 'Europe/Berlin');
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('userLocale', 'de-DE');
  });

  it('provides stable function references across re-renders', () => {
    let firstRenderFunctions: any;

    const FunctionRefComponent = () => {
      const context = useTimezone();

      if (!firstRenderFunctions) {
        firstRenderFunctions = {
          setUserTimezone: context.setUserTimezone,
          detectSystemTimezone: context.detectSystemTimezone,
          getTimezoneOffset: context.getTimezoneOffset
        };
      }

      const isStable =
        Object.is(context.setUserTimezone, firstRenderFunctions.setUserTimezone) &&
        Object.is(context.detectSystemTimezone, firstRenderFunctions.detectSystemTimezone) &&
        Object.is(context.getTimezoneOffset, firstRenderFunctions.getTimezoneOffset);

      return (
        <div data-testid="functions-stable">
          {isStable ? 'stable' : 'changed'}
        </div>
      );
    };

    const { rerender } = render(
      <TimezoneProvider>
        <FunctionRefComponent />
      </TimezoneProvider>
    );

    expect(screen.getByTestId('functions-stable')).toHaveTextContent('stable');

    rerender(
      <TimezoneProvider>
        <FunctionRefComponent />
      </TimezoneProvider>
    );

    expect(screen.getByTestId('functions-stable')).toHaveTextContent('stable');
  });
});

describe('COMMON_TIMEZONES', () => {
  it('exports common timezone options', () => {
    expect(COMMON_TIMEZONES).toBeDefined();
    expect(Array.isArray(COMMON_TIMEZONES)).toBe(true);
    expect(COMMON_TIMEZONES.length).toBeGreaterThan(0);
  });

  it('contains expected US timezones', () => {
    const usTimezones = COMMON_TIMEZONES.filter(tz => tz.group === 'US');

    // Test that US timezone group exists and has proper structure
    expect(usTimezones.length).toBeGreaterThan(0);

    // Test that all US timezones have America/ prefix
    usTimezones.forEach(tz => {
      expect(tz.value).toMatch(/^America\/)/);
      expect(tz.group).toBe('US');
      expect(typeof tz.label).toBe('string');
    });

    // Test for presence of major US timezones (behavioral, not hardcoded)
    const timezoneValues = usTimezones.map(tz => tz.value);
    const hasEasternTime = timezoneValues.some(tz => tz.includes('New_York'));
    const hasCentralTime = timezoneValues.some(tz => tz.includes('Chicago'));
    const hasPacificTime = timezoneValues.some(tz => tz.includes('Los_Angeles'));

    expect(hasEasternTime).toBe(true);
    expect(hasCentralTime).toBe(true);
    expect(hasPacificTime).toBe(true);
  });

  it('contains international timezones', () => {
    const intlTimezones = COMMON_TIMEZONES.filter(tz => tz.group === 'International');

    // Test that international timezone group exists
    expect(intlTimezones.length).toBeGreaterThan(0);

    // Test structure of international timezones
    intlTimezones.forEach(tz => {
      expect(tz.group).toBe('International');
      expect(typeof tz.value).toBe('string');
      expect(typeof tz.label).toBe('string');
    });

    // Test for presence of UTC and major international timezones (behavioral)
    const timezoneValues = intlTimezones.map(tz => tz.value);
    const hasUTC = timezoneValues.includes('UTC');
    const hasEuropeanTimezone = timezoneValues.some(tz => tz.startsWith('Europe/'));
    const hasAsianTimezone = timezoneValues.some(tz => tz.startsWith('Asia/'));

    expect(hasUTC).toBe(true);
    expect(hasEuropeanTimezone).toBe(true);
    expect(hasAsianTimezone).toBe(true);
  });

  it('has proper structure for all timezone entries', () => {
    COMMON_TIMEZONES.forEach(timezone => {
      expect(timezone).toHaveProperty('value');
      expect(timezone).toHaveProperty('label');
      expect(timezone).toHaveProperty('group');
      expect(typeof timezone.value).toBe('string');
      expect(typeof timezone.label).toBe('string');
      expect(typeof timezone.group).toBe('string');
      expect(['US', 'International']).toContain(timezone.group);
    });
  });
});
