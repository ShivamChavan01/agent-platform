import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../App";
import { ApiError } from "../lib/api";
import { Icon } from "../components/Icon";
import { Logo } from "../components/Logo";

type Mode = "signin" | "signup";

export function Login() {
  const { authed, login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    try {
      if (mode === "signin") {
        await login(email, password);
      } else {
        await register(name.trim() || undefined, email, password);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  if (authed) {
    return <Navigate to="/app" replace />;
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-logo">
          <span className="auth-logo-icon">
            <Logo size={20} />
          </span>
          <span className="auth-logo-text">openagent</span>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === "signin" ? "active" : ""}`}
            onClick={() => {
              setMode("signin");
              setError(null);
            }}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${mode === "signup" ? "active" : ""}`}
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={submit}>
          {mode === "signup" && (
            <div className="form-group">
              <label className="form-label" htmlFor="name">
                Full Name
              </label>
              <input
                id="name"
                className="form-input"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              className="form-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <div className="password-wrap">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                className="form-input"
                style={{ paddingRight: 36 }}
                placeholder={mode === "signup" ? "Create a password (8+ chars)" : "Your password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
              >
                <Icon name={showPassword ? "eyeOff" : "eye"} size={16} />
              </button>
            </div>
          </div>

          {mode === "signin" && (
            <div className="form-row">
              <label className="checkbox-label">
                <input type="checkbox" defaultChecked />
                Remember me
              </label>
            </div>
          )}

          {error && <div className="error-msg visible">{error}</div>}

          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "signin" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
