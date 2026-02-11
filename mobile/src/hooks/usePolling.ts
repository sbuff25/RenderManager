/**
 * Auto-refresh hook — polls the Wain API at a regular interval
 */

import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Polls `fetcher` every `intervalMs` milliseconds.
 * Returns the latest data, loading state, error, and a manual refresh fn.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled: boolean = true,
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const doFetch = useCallback(async () => {
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result);
        setError(null);
        setLoading(false);
      }
    } catch (e: any) {
      if (mountedRef.current) {
        setError(e.message || 'Connection failed');
        setLoading(false);
      }
    }
  }, [fetcher]);

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled) {
      setLoading(false);
      return;
    }

    setLoading(true);
    doFetch();

    timerRef.current = setInterval(doFetch, intervalMs);

    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [doFetch, intervalMs, enabled]);

  const refresh = useCallback(() => {
    doFetch();
  }, [doFetch]);

  return { data, loading, error, refresh };
}
