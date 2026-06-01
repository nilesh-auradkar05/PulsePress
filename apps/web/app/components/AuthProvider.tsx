"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, clearToken, getToken, setToken, type User } from "../lib/api";

type AuthState = {
  user: User | null;
  isLoggedIn: boolean;
  loading: boolean;
  login: (email: string) => Promise<void>;
  register: (email: string, displayName: string) => Promise<void>;
  logout: () => void;
  revalidate: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

function hasStoredToken(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return Boolean(getToken());
}

/**
 * Auth state backed by the PulsePress API. In local dev the API exposes an
 * explicit passwordless shortcut (`/local/auth/*`); production uses Cognito
 * PKCE. The token is kept in sessionStorage and used as a Bearer credential.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(hasStoredToken);

  useEffect(() => {
    const token = getToken();

    if (!token) {
      return;
    }

    let cancelled = false;

    api
      .me()
      .then((currentUser) => {
        if (!cancelled) {
          setUser(currentUser);
        }
      })
      .catch(() => {
        clearToken();

        if (!cancelled) {
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string) => {
    const res = await api.login(email);
    setToken(res.access_token);
    setUser(res.user);
    setLoading(false);
  }, []);

  const register = useCallback(async (email: string, displayName: string) => {
    const res = await api.register(email, displayName);
    setToken(res.access_token);
    setUser(res.user);
    setLoading(false);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setLoading(false);
  }, []);

  /**
   * Re-sync auth state with the stored token. Needed when a page is restored
   * from the browser's back/forward (bfcache) cache: React state is frozen at
   * restore time, so a user who signed out and pressed Back would otherwise keep
   * stale `user` state. Reading the token authority fixes that.
   */
  const revalidate = useCallback(() => {
    const token = getToken();

    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    if (user) {
      return;
    }

    setLoading(true);
    api
      .me()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [user]);

  const value = useMemo<AuthState>(
    () => ({ user, isLoggedIn: user !== null, loading, login, register, logout, revalidate }),
    [user, loading, login, register, logout, revalidate],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);

  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return ctx;
}
