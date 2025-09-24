import { useCallback, useEffect, useState } from 'react';
import {
  type AdminRole,
  type AdminSessionData,
  getAdminSession,
} from '@/services/adminApi';

interface AdminSessionState {
  loading: boolean;
  session: AdminSessionData | null;
  error: Error | null;
}

let cachedSession: AdminSessionData | null = null;
let cachedError: Error | null = null;
let inflight: Promise<AdminSessionData> | null = null;

async function fetchSession(forceRefresh: boolean): Promise<AdminSessionData> {
  if (!forceRefresh) {
    if (cachedSession) {
      return cachedSession;
    }
    if (inflight) {
      return inflight;
    }
  }

  inflight = getAdminSession()
    .then(res => {
      if (res.code !== 0) {
        throw new Error(`admin session rejected with code ${res.code}`);
      }
      cachedSession = res.data;
      cachedError = null;
      return res.data;
    })
    .catch(err => {
      cachedSession = null;
      cachedError = err instanceof Error ? err : new Error(String(err));
      throw cachedError;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

export interface UseAdminSessionResult extends AdminSessionState {
  roles: AdminRole[];
  refresh: (forceRefresh?: boolean) => Promise<void>;
}

export function useAdminSession(): UseAdminSessionResult {
  const [state, setState] = useState<AdminSessionState>(() => ({
    loading: cachedSession === null && cachedError === null,
    session: cachedSession,
    error: cachedError,
  }));

  useEffect(() => {
    let cancelled = false;
    if (cachedSession || cachedError) {
      setState({
        loading: false,
        session: cachedSession,
        error: cachedError,
      });
      return;
    }

    fetchSession(false)
      .then(data => {
        if (!cancelled) {
          setState({ loading: false, session: data, error: null });
        }
      })
      .catch(err => {
        if (!cancelled) {
          setState({ loading: false, session: null, error: err instanceof Error ? err : new Error(String(err)) });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = useCallback(async (forceRefresh = true) => {
    setState(prev => ({ ...prev, loading: true }));
    try {
      const data = await fetchSession(forceRefresh);
      setState({ loading: false, session: data, error: null });
    } catch (err) {
      setState({
        loading: false,
        session: null,
        error: err instanceof Error ? err : new Error(String(err)),
      });
    }
  }, []);

  return {
    ...state,
    roles: state.session?.roles ?? [],
    refresh,
  };
}

export function resetAdminSessionCache(): void {
  cachedSession = null;
  cachedError = null;
  inflight = null;
}
