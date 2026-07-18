"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getSession, login as loginRequest, logout as logoutRequest } from "@/lib/api";
import type { User } from "@/types/dashboard";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const session = await getSession();
    setUser(session.user);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh().catch(() => {
      setUser(null);
      setLoading(false);
    });
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (username, password) => {
        const result = await loginRequest(username, password);
        setUser(result.user);
      },
      logout: async () => {
        await logoutRequest();
        setUser(null);
      },
      refresh,
    }),
    [loading, refresh, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
