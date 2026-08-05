import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { authApi, loadStoredAuth, type AuthState } from "./auth";
import type { User } from "./lib/types";
import { Logo } from "./components/Logo";
import { ToastProvider } from "./components/Toast";

const Login = lazy(() => import("./pages/Login").then((m) => ({ default: m.Login })));
const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const Workspace = lazy(() => import("./pages/Workspace").then((m) => ({ default: m.Workspace })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));

function PageLoader() {
  return (
    <div className="app-loading">
      <span className="spin-logo">
        <Logo size={24} />
      </span>
    </div>
  );
}

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
        <Suspense fallback={<PageLoader />}>
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
        </Suspense>
      </ToastProvider>
    </AuthProvider>
  );
}
