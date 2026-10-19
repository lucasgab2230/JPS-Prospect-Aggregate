import { useTimezone } from '@/contexts/TimezoneContext';
import { formatDate, DateFormat, DateFormatOptions } from '@/utils/dateUtils';

/**
 * Hook for timezone-aware date formatting using user's preferences
 */
export function useTimezoneDate() {
  const { timezone, locale } = useTimezone();

  const formatUserDate = (
    dateString: string | null | undefined,
    format: DateFormat = 'datetime',
    options: Partial<DateFormatOptions> = {}
  ) => {
    return formatDate(dateString, {
      timezone,
      locale,
      format,
      ...options
    });
  };

  const formatAIEnhanced = (dateString: string | null | undefined) => {
    if (!dateString) return 'Not enhanced';

    return `AI Enhanced on ${formatDate(dateString, {
      timezone,
      locale,
      format: 'datetime'
    })}`;
  };

  const formatLastProcessed = (dateString: string | null | undefined) => {
    if (!dateString) return 'Never processed';

    return formatDate(dateString, {
      timezone,
      locale,
      format: 'datetime-with-tz'
    });
  };

  const formatQueueTime = (dateString: string | null | undefined) => {
    return formatDate(dateString, {
      timezone,
      locale,
      format: 'time',
      showTimezone: true
    });
  };

  return {
    formatUserDate,
    formatAIEnhanced,
    formatLastProcessed,
    formatQueueTime,
    timezone,
    locale
  };
}
