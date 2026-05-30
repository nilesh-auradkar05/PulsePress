"use client";

import { createContext, useContext, useMemo, useState } from "react";

type AuthState = {
  isLoggedIn: boolean;
  login: () => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

/**
 * Placeholder auth state for the walking-skeleton UI. Mirrors the design's
 * fake `onLoginSuccess` flow; the real Cognito Authorization-Code + PKCE flow
 * replaces this in a later sprint (CLAUDE.md §10, SPEC §14).
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const value = useMemo<AuthState>(
    () => ({
      isLoggedIn,
      login: () => setIsLoggedIn(true),
      logout: () => setIsLoggedIn(false),
    }),
    [isLoggedIn],
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
