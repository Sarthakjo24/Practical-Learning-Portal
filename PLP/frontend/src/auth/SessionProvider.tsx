import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { UserProfile } from "../types";

interface SessionContextValue {
  user: UserProfile | null;
  loading: boolean;
  refreshSession: () => Promise<void>;
  login: (provider: "google" | "microsoft", nextPath?: string) => void;
  logout: (redirectPath?: string) => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const sessionUser = await api.session();
      setUser(sessionUser);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  const logout = useCallback(async (redirectPath = "/login") => {
    await api.logout();
    setUser(null);
    window.location.href = redirectPath;
  }, []);

  const login = useCallback((provider: "google" | "microsoft", nextPath = "/dashboard") => {
    window.location.href = api.authLoginUrl(provider, nextPath);
  }, []);

  const value = useMemo(
    () => ({ user, loading, refreshSession, login, logout }),
    [user, loading, refreshSession, login, logout]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider.");
  }
  return context;
}
