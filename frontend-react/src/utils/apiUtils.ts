/**
 * API utilities for consistent HTTP request handling across the application
 */

export interface ApiError extends Error {
  status?: number;
  statusText?: string;
}

export interface RetryOptions {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  retryCondition?: (error: Error) => boolean;
}

export interface RequestInterceptor {
  (url: string, options: RequestInit): Promise<{ url: string; options: RequestInit }> | { url: string; options: RequestInit };
}

export interface ResponseInterceptor {
  (response: Response): Promise<Response> | Response;
}

export interface ErrorInterceptor {
  (error: Error): Promise<Error> | Error;
}

export interface FetchOptions extends RequestInit {
  timeout?: number;
  retry?: RetryOptions;
  skipInterceptors?: boolean;
  abortController?: AbortController;
  deduplicate?: boolean;
  deduplicationKey?: string;
}

/**
 * Default retry condition - retry on network errors and server errors (5xx)
 */
const defaultRetryCondition = (error: Error): boolean => {
  if (error.message.includes('Network error') || error.message.includes('timeout')) {
    return true;
  }
  if ('status' in error && typeof error.status === 'number') {
    return error.status >= 500;
  }
  return false;
};

/**
 * Sleep utility for retry delays
 */
const sleep = (ms: number): Promise<void> => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Calculate exponential backoff delay with jitter
 */
const calculateRetryDelay = (attempt: number, baseDelay: number, maxDelay: number): number => {
  const exponentialDelay = baseDelay * Math.pow(2, attempt);
  const jitter = Math.random() * 0.1 * exponentialDelay; // Add 10% jitter
  return Math.min(exponentialDelay + jitter, maxDelay);
};

/**
 * Global interceptor storage
 */
const interceptors = {
  request: [] as RequestInterceptor[],
  response: [] as ResponseInterceptor[],
  error: [] as ErrorInterceptor[],
};

/**
 * Request deduplication storage
 */
const pendingRequests = new Map<string, Promise<unknown>>();

/**
 * Generate a deduplication key for a request
 */
const generateDeduplicationKey = (url: string, options: RequestInit): string => {
  const method = options.method || 'GET';
  const bodyHash = options.body ? btoa(JSON.stringify(options.body)) : '';
  const headersHash = options.headers ? btoa(JSON.stringify(options.headers)) : '';
  return `${method}:${url}:${bodyHash}:${headersHash}`;
};

/**
 * Add a request interceptor
 */
export const addRequestInterceptor = (interceptor: RequestInterceptor): (() => void) => {
  interceptors.request.push(interceptor);
  return () => {
    const index = interceptors.request.indexOf(interceptor);
    if (index > -1) {
      interceptors.request.splice(index, 1);
    }
  };
};

/**
 * Add a response interceptor
 */
export const addResponseInterceptor = (interceptor: ResponseInterceptor): (() => void) => {
  interceptors.response.push(interceptor);
  return () => {
    const index = interceptors.response.indexOf(interceptor);
    if (index > -1) {
      interceptors.response.splice(index, 1);
    }
  };
};

/**
 * Add an error interceptor
 */
export const addErrorInterceptor = (interceptor: ErrorInterceptor): (() => void) => {
  interceptors.error.push(interceptor);
  return () => {
    const index = interceptors.error.indexOf(interceptor);
    if (index > -1) {
      interceptors.error.splice(index, 1);
    }
  };
};

/**
 * Apply request interceptors
 */
const applyRequestInterceptors = async (url: string, options: RequestInit): Promise<{ url: string; options: RequestInit }> => {
  let result = { url, options };

  for (const interceptor of interceptors.request) {
    result = await interceptor(result.url, result.options);
  }

  return result;
};

/**
 * Apply response interceptors
 */
const applyResponseInterceptors = async (response: Response): Promise<Response> => {
  let result = response;

  for (const interceptor of interceptors.response) {
    result = await interceptor(result);
  }

  return result;
};

/**
 * Apply error interceptors
 */
const applyErrorInterceptors = async (error: Error): Promise<Error> => {
  let result = error;

  for (const interceptor of interceptors.error) {
    result = await interceptor(result);
  }

  return result;
};

/**
 * Enhanced fetch with retry logic, consistent error handling and timeout support
 * @param url - Request URL
 * @param options - Fetch options with optional timeout and retry configuration
 * @returns Promise resolving to parsed JSON response
 * @throws ApiError with detailed error information
 */
export const fetchWithErrorHandling = async <T = unknown>(
  url: string,
  options: FetchOptions = {}
): Promise<T> => {
  const {
    timeout = 30000,
    retry = {},
    skipInterceptors = false,
    abortController,
    deduplicate = false,
    deduplicationKey,
    ...fetchOptions
  } = options;

  // Always include credentials for cookie-based authentication
  const finalFetchOptions: RequestInit = {
    credentials: 'include' as RequestCredentials,
    ...fetchOptions
  };

  // Retry options will be handled in executeRequest function

  // Apply request interceptors
  let requestParams = { url, options: finalFetchOptions };
  if (!skipInterceptors) {
    requestParams = await applyRequestInterceptors(url, finalFetchOptions);
  }

  // Handle request deduplication
  const finalDeduplicationKey = deduplicationKey || generateDeduplicationKey(requestParams.url, requestParams.options);

  if (deduplicate) {
    const existingRequest = pendingRequests.get(finalDeduplicationKey);
    if (existingRequest) {
      return existingRequest as Promise<T>;
    }
  }

  // Create the actual request promise
  const requestPromise = executeRequest<T>(requestParams, timeout, retry, abortController, skipInterceptors);

  // Store the request for deduplication
  if (deduplicate) {
    pendingRequests.set(finalDeduplicationKey, requestPromise);

    // Clean up after request completes (success or failure)
    requestPromise.finally(() => {
      pendingRequests.delete(finalDeduplicationKey);
    });
  }

  return requestPromise;
};

/**
 * Execute the actual HTTP request with retry logic
 */
const executeRequest = async <T = unknown>(
  requestParams: { url: string; options: RequestInit },
  timeout: number,
  retry: RetryOptions,
  abortController?: AbortController,
  skipInterceptors: boolean = false
): Promise<T> => {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    maxDelay = 10000,
    retryCondition = defaultRetryCondition
  } = retry;

  let lastError: Error = new Error('Unknown error');

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    // Create combined abort controller that responds to both timeout and external cancellation
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // If external abort controller is provided, abort when it aborts
    const abortHandler = () => controller.abort();
    if (abortController) {
      if (abortController.signal.aborted) {
        throw new Error('Request was cancelled');
      }
      abortController.signal.addEventListener('abort', abortHandler);
    }

    try {
      let response = await fetch(requestParams.url, {
        ...requestParams.options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Apply response interceptors
      if (!skipInterceptors) {
        response = await applyResponseInterceptors(response);
      }

      if (!response.ok) {
        // Try to get error details from response
        let errorData: { error?: string; message?: string } = {};
        try {
          errorData = await response.json();
        } catch {
          // If JSON parsing fails, use default error structure
          errorData = {
            error: `HTTP ${response.status}: ${response.statusText}`,
            message: `Request failed with status ${response.status}`,
          };
        }

        const apiError = new Error(
          errorData.error || errorData.message || `Request failed: ${response.statusText}`
        ) as ApiError;

        apiError.status = response.status;
        apiError.statusText = response.statusText;

        throw apiError;
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      } else {
        return await response.text() as T;
      }
    } catch (error) {
      clearTimeout(timeoutId);

      // Clean up abort event listener
      if (abortController) {
        abortController.signal.removeEventListener('abort', abortHandler);
      }

      if (error instanceof Error && error.name === 'AbortError') {
        // Check if it was cancelled externally or timed out
        if (abortController?.signal.aborted) {
          lastError = new Error('Request was cancelled');
        } else {
          lastError = new Error(`Request timeout after ${timeout}ms`);
        }
      } else if (error instanceof Error && 'status' in error) {
        // API errors (4xx, 5xx)
        lastError = error;
      } else {
        // Network errors
        lastError = new Error(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }

      // Apply error interceptors
      if (!skipInterceptors) {
        lastError = await applyErrorInterceptors(lastError);
      }

      // Check if we should retry
      if (attempt < maxRetries && retryCondition(lastError)) {
        const delay = calculateRetryDelay(attempt, baseDelay, maxDelay);
        await sleep(delay);
        continue; // Retry the request
      }

      // No more retries or error is not retryable
      throw lastError;
    }
  }

  // This should never be reached, but TypeScript needs it
  throw lastError;
};

/**
 * GET request with error handling
 * @param url - Request URL
 * @param options - Fetch options
 * @returns Promise resolving to parsed JSON response
 */
export const get = <T = unknown>(url: string, options: FetchOptions = {}): Promise<T> => {
  return fetchWithErrorHandling<T>(url, {
    ...options,
    method: 'GET',
  });
};

/**
 * POST request with error handling
 * @param url - Request URL
 * @param data - Request body data
 * @param options - Fetch options
 * @returns Promise resolving to parsed JSON response
 */
export const post = <T = unknown>(
  url: string,
  data?: unknown,
  options: FetchOptions = {}
): Promise<T> => {
  return fetchWithErrorHandling<T>(url, {
    ...options,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * PUT request with error handling
 * @param url - Request URL
 * @param data - Request body data
 * @param options - Fetch options
 * @returns Promise resolving to parsed JSON response
 */
export const put = <T = unknown>(
  url: string,
  data?: unknown,
  options: FetchOptions = {}
): Promise<T> => {
  return fetchWithErrorHandling<T>(url, {
    ...options,
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * DELETE request with error handling
 * @param url - Request URL
 * @param options - Fetch options
 * @returns Promise resolving to parsed JSON response
 */
export const del = <T = unknown>(url: string, options: FetchOptions = {}): Promise<T> => {
  return fetchWithErrorHandling<T>(url, {
    ...options,
    method: 'DELETE',
  });
};

/**
 * GET request with predefined configuration for data fetching
 * @param url - Request URL
 * @param options - Additional fetch options (will merge with data config)
 * @returns Promise resolving to parsed JSON response
 */
export const getData = <T = unknown>(url: string, options: Omit<FetchOptions, 'timeout' | 'retry'> = {}): Promise<T> => {
  return get<T>(url, {
    ...REQUEST_CONFIGS.data,
    ...options,
  });
};

/**
 * GET request with automatic deduplication for data fetching
 * Prevents duplicate requests to the same endpoint with same parameters
 * @param url - Request URL
 * @param options - Additional fetch options (will merge with data config)
 * @returns Promise resolving to parsed JSON response
 */
export const getDataDeduped = <T = unknown>(url: string, options: Omit<FetchOptions, 'timeout' | 'retry' | 'deduplicate'> = {}): Promise<T> => {
  return get<T>(url, {
    ...REQUEST_CONFIGS.data,
    deduplicate: true,
    ...options,
  });
};

/**
 * POST request with predefined configuration for data operations
 * @param url - Request URL
 * @param data - Request body data
 * @param options - Additional fetch options (will merge with data config)
 * @returns Promise resolving to parsed JSON response
 */
export const postData = <T = unknown>(
  url: string,
  data?: unknown,
  options: Omit<FetchOptions, 'timeout' | 'retry'> = {}
): Promise<T> => {
  return post<T>(url, data, {
    ...REQUEST_CONFIGS.data,
    ...options,
  });
};

/**
 * GET request with predefined configuration for authentication
 * @param url - Request URL
 * @param options - Additional fetch options (will merge with auth config)
 * @returns Promise resolving to parsed JSON response
 */
export const getAuth = <T = unknown>(url: string, options: Omit<FetchOptions, 'timeout' | 'retry'> = {}): Promise<T> => {
  return get<T>(url, {
    ...REQUEST_CONFIGS.auth,
    ...options,
  });
};

/**
 * POST request with predefined configuration for authentication
 * @param url - Request URL
 * @param data - Request body data
 * @param options - Additional fetch options (will merge with auth config)
 * @returns Promise resolving to parsed JSON response
 */
export const postAuth = <T = unknown>(
  url: string,
  data?: unknown,
  options: Omit<FetchOptions, 'timeout' | 'retry'> = {}
): Promise<T> => {
  return post<T>(url, data, {
    ...REQUEST_CONFIGS.auth,
    ...options,
  });
};

/**
 * GET request with predefined configuration for polling operations
 * @param url - Request URL
 * @param options - Additional fetch options (will merge with polling config)
 * @returns Promise resolving to parsed JSON response
 */
export const getPolling = <T = unknown>(url: string, options: Omit<FetchOptions, 'timeout' | 'retry'> = {}): Promise<T> => {
  return get<T>(url, {
    ...REQUEST_CONFIGS.polling,
    ...options,
  });
};

/**
 * GET request with automatic deduplication for polling operations
 * Prevents multiple simultaneous polling requests to the same endpoint
 * @param url - Request URL
 * @param options - Additional fetch options (will merge with polling config)
 * @returns Promise resolving to parsed JSON response
 */
export const getPollingDeduped = <T = unknown>(url: string, options: Omit<FetchOptions, 'timeout' | 'retry' | 'deduplicate'> = {}): Promise<T> => {
  return get<T>(url, {
    ...REQUEST_CONFIGS.polling,
    deduplicate: true,
    ...options,
  });
};

/**
 * POST request with predefined configuration for long-running processing operations
 * @param url - Request URL
 * @param data - Request body data
 * @param options - Additional fetch options (will merge with processing config)
 * @returns Promise resolving to parsed JSON response
 */
export const postProcessing = <T = unknown>(
  url: string,
  data?: unknown,
  options: Omit<FetchOptions, 'timeout' | 'retry'> = {}
): Promise<T> => {
  return post<T>(url, data, {
    ...REQUEST_CONFIGS.processing,
    ...options,
  });
};

/**
 * Handles common API response patterns
 * @param response - API response with status and data structure
 * @returns The data portion of the response
 * @throws Error if response indicates failure
 */
export const handleApiResponse = <T = unknown>(response: {
  status: string;
  data?: T;
  message?: string;
  error?: string;
}): T => {
  if (response.status === 'success' && response.data) {
    return response.data;
  }

  if (response.status === 'error') {
    throw new Error(response.error || response.message || 'API request failed');
  }

  throw new Error('Invalid API response format');
};

/**
 * Creates query string from object parameters
 * @param params - Object with query parameters
 * @returns URL-encoded query string
 */
export const buildQueryString = (params: Record<string, string | number | boolean | undefined | null | Array<string | number>>): string => {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      if (Array.isArray(value)) {
        // Handle arrays by adding multiple params with the same key
        value.forEach(item => {
          searchParams.append(key, String(item));
        });
      } else {
        searchParams.append(key, String(value));
      }
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
};

/**
 * Utility for building API URLs with base path and query parameters
 * @param endpoint - API endpoint path
 * @param params - Query parameters
 * @param baseUrl - Base URL (defaults to current origin)
 * @returns Complete URL string
 */
export const buildApiUrl = (
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined | null>,
  baseUrl?: string
): string => {
  const base = baseUrl || '';
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const query = params ? buildQueryString(params) : '';

  return `${base}${path}${query}`;
};

/**
 * Predefined timeout configurations for different request types
 */
export const TIMEOUT_CONFIGS = {
  SHORT: 5000,      // 5 seconds - for auth checks, quick status updates
  MEDIUM: 30000,    // 30 seconds - for data fetching, standard operations
  LONG: 300000,     // 5 minutes - for processing operations, file uploads
  POLLING: 10000,   // 10 seconds - for polling operations
} as const;

/**
 * Request type configurations with appropriate timeouts and retry settings
 */
export const REQUEST_CONFIGS = {
  auth: {
    timeout: TIMEOUT_CONFIGS.SHORT,
    retry: { maxRetries: 2, baseDelay: 500, maxDelay: 2000 }
  },
  data: {
    timeout: TIMEOUT_CONFIGS.MEDIUM,
    retry: { maxRetries: 3, baseDelay: 1000, maxDelay: 5000 }
  },
  processing: {
    timeout: TIMEOUT_CONFIGS.LONG,
    retry: { maxRetries: 2, baseDelay: 2000, maxDelay: 10000 }
  },
  polling: {
    timeout: TIMEOUT_CONFIGS.POLLING,
    retry: { maxRetries: 1, baseDelay: 1000, maxDelay: 3000 }
  },
  upload: {
    timeout: TIMEOUT_CONFIGS.LONG,
    retry: { maxRetries: 2, baseDelay: 3000, maxDelay: 15000 }
  }
} as const;

/**
 * Create an AbortController that can be used to cancel requests
 * @returns AbortController instance
 */
export const createCancellableRequest = (): AbortController => {
  return new AbortController();
};

/**
 * Create a timeout-based AbortController
 * @param timeoutMs - Timeout in milliseconds
 * @returns AbortController that will abort after the specified timeout
 */
export const createTimeoutController = (timeoutMs: number): AbortController => {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller;
};

/**
 * Combine multiple AbortControllers into one
 * @param controllers - Array of AbortControllers
 * @returns New AbortController that aborts when any of the input controllers abort
 */
export const combineAbortControllers = (controllers: AbortController[]): AbortController => {
  const combinedController = new AbortController();

  const abortHandler = () => combinedController.abort();

  for (const controller of controllers) {
    if (controller.signal.aborted) {
      combinedController.abort();
      break;
    }
    controller.signal.addEventListener('abort', abortHandler);
  }

  // Cleanup function to remove event listeners
  const cleanup = () => {
    for (const controller of controllers) {
      controller.signal.removeEventListener('abort', abortHandler);
    }
  };

  // Store cleanup function on the controller for later use
  (combinedController as AbortController & { cleanup: () => void }).cleanup = cleanup;

  return combinedController;
};
