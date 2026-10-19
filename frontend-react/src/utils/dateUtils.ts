/**
 * Date formatting utilities for consistent date display across the application
 * Now supports user-specific timezones and enhanced formatting options
 */

export type DateFormat = 'date' | 'datetime' | 'time' | 'relative' | 'datetime-with-tz' | 'date-with-time';

export interface DateFormatOptions {
  fallback?: string;
  format?: DateFormat;
  locale?: string;
  timezone?: string;
  showTimezone?: boolean;
}

/**
 * Formats a date string consistently across the application with timezone support
 * @param dateString - ISO date string or null
 * @param options - Formatting options including timezone
 * @returns Formatted date string
 */
export const formatDate = (
  dateString: string | null | undefined,
  options: DateFormatOptions = {}
): string => {
  const {
    fallback = 'N/A',
    format = 'datetime',
    locale = 'en-US',
    timezone,
    showTimezone = false
  } = options;

  if (!dateString) return fallback;

  try {
    // Ensure proper ISO format by adding Z if timezone info is missing
    const dateStr = dateString.includes('Z') || dateString.includes('+') || dateString.includes('-')
      ? dateString
      : dateString + 'Z';

    const date = new Date(dateStr);

    // Check if date is valid
    if (isNaN(date.getTime())) {
      // Invalid date string, using fallback
      return fallback;
    }

    // Create formatting options with timezone support
    const formatOptions: Intl.DateTimeFormatOptions = {};

    if (timezone) {
      formatOptions.timeZone = timezone;
    }

    switch (format) {
      case 'date':
        formatOptions.year = 'numeric';
        formatOptions.month = 'numeric';
        formatOptions.day = 'numeric';
        break;
      case 'time':
        formatOptions.hour = 'numeric';
        formatOptions.minute = '2-digit';
        formatOptions.hour12 = true;
        if (showTimezone) formatOptions.timeZoneName = 'short';
        break;
      case 'datetime':
        formatOptions.year = 'numeric';
        formatOptions.month = 'numeric';
        formatOptions.day = 'numeric';
        formatOptions.hour = 'numeric';
        formatOptions.minute = '2-digit';
        formatOptions.hour12 = true;
        if (showTimezone) formatOptions.timeZoneName = 'short';
        break;
      case 'datetime-with-tz':
        formatOptions.year = 'numeric';
        formatOptions.month = 'numeric';
        formatOptions.day = 'numeric';
        formatOptions.hour = 'numeric';
        formatOptions.minute = '2-digit';
        formatOptions.hour12 = true;
        formatOptions.timeZoneName = 'short';
        break;
      case 'date-with-time':
        formatOptions.year = 'numeric';
        formatOptions.month = 'short';
        formatOptions.day = 'numeric';
        formatOptions.hour = 'numeric';
        formatOptions.minute = '2-digit';
        formatOptions.hour12 = true;
        if (showTimezone) formatOptions.timeZoneName = 'short';
        break;
      case 'relative':
        return formatRelativeTime(date, timezone);
      default:
        formatOptions.year = 'numeric';
        formatOptions.month = 'numeric';
        formatOptions.day = 'numeric';
        formatOptions.hour = 'numeric';
        formatOptions.minute = '2-digit';
        formatOptions.hour12 = true;
        break;
    }

    return new Intl.DateTimeFormat(locale, formatOptions).format(date);
  } catch (_error) {
    // Error formatting date, using fallback
    return fallback;
  }
};

/**
 * Formats a date as relative time (e.g., "2 hours ago", "3 days ago")
 * @param date - Date object
 * @param timezone - Optional timezone for fallback formatting
 * @returns Relative time string
 */
export const formatRelativeTime = (date: Date, timezone?: string): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) {
    return 'Just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  } else {
    // For older dates, show formatted date in user's timezone
    if (timezone) {
      return new Intl.DateTimeFormat('en-US', {
        timeZone: timezone,
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      }).format(date);
    }
    return date.toLocaleDateString();
  }
};

/**
 * Checks if a date string is today
 * @param dateString - ISO date string
 * @returns True if the date is today
 */
export const isToday = (dateString: string | null): boolean => {
  if (!dateString) return false;

  try {
    const date = new Date(dateString);
    const today = new Date();
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    );
  } catch {
    return false;
  }
};

/**
 * Checks if a date is in the future
 * @param dateString - ISO date string
 * @returns True if the date is in the future
 */
export const isFuture = (dateString: string | null): boolean => {
  if (!dateString) return false;

  try {
    const date = new Date(dateString);
    return date > new Date();
  } catch {
    return false;
  }
};

/**
 * Creates a timezone-aware date formatter function
 * @param timezone - User's timezone
 * @param locale - User's locale
 * @returns Function that formats dates with user's timezone/locale
 */
export const createTimezoneFormatter = (timezone: string, locale: string = 'en-US') => {
  return (dateString: string | null | undefined, format: DateFormat = 'datetime', options: Partial<DateFormatOptions> = {}) => {
    return formatDate(dateString, {
      timezone,
      locale,
      format,
      ...options
    });
  };
};
