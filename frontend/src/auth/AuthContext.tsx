import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, getToken, setToken, type Role, type User } from "../lib/api";

type AuthState = {
  user: User | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
  /** UI convenience only — the backend enforces this independently on
   * every restricted route, so hiding a button is never the control. */
  can: (action: "cancel_documents" | "edit_masters") => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.get<User>("/auth/me");
        if (!cancelled) setUser(me);
      } catch {
        setToken(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const { access_token } = await api.postForm<{ access_token: string }>("/auth/login", {
      username,
      password,
    });
    setToken(access_token);
    setUser(await api.get<User>("/auth/me"));
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const can = useCallback(
    (action: "cancel_documents" | "edit_masters") => {
      const privileged: Role[] = ["admin", "owner"];
      if (!user) return false;
      switch (action) {
        case "cancel_documents":
        case "edit_masters":
          return privileged.includes(user.role);
      }
    },
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, signIn, signOut, can }),
    [user, loading, signIn, signOut, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
