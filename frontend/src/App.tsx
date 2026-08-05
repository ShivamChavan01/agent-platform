import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { authApi, loadStoredAuth, type AuthState } from "./auth";
import type { User } from "./lib/types";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Workspace } from "./pages/Workspace";
import { Settings } from "./pages/Settings";
import { ToastProvider } from "./components/Toast";

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  updateUser: () => {},
  authed: false,
});

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const stored = loadStoredAuth();
  const [state, setState] = useState({ user: stored.user, token: stored.token });

  const login = useCallback(async (email: string, password: string) => {
    const user = await authApi.login(email, password);
    setState({ user, token: authToken() });
  }, []);

  const register = useCallback(async (name: string | undefined, email: string, password: string) => {
    const user = await authApi.register(name, email, password);
    setState({ user, token: authToken() });
  }, []);

  const logout = useCallback(() => {
    authApi.logout();
    setState({ user: null, token: null });
  }, []);

  const updateUser = useCallback((user: User) => {
    setState((s) => ({ ...s, user }));
    localStorage.setItem("aw_user", JSON.stringify(user));
  }, []);

  useEffect(() => {
    const onUnauthorized = () => logout();
    window.addEventListener("aw:unauthorized", onUnauthorized);
    return () => window.removeEventListener("aw:unauthorized", onUnauthorized);
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        updateUser,
        authed: Boolean(state.token),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function authToken(): string {
  return localStorage.getItem("aw_token") ?? "";
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { authed } = useAuth();
  if (!authed) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/app"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/app/projects/:projectId"
          element={
            <RequireAuth>
              <Workspace />
            </RequireAuth>
          }
        />
        <Route
          path="/app/projects/:projectId/conversations/:conversationId"
          element={
            <RequireAuth>
              <Workspace />
            </RequireAuth>
          }
        />
        <Route
          path="/app/settings"
          element={
            <RequireAuth>
              <Settings />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
