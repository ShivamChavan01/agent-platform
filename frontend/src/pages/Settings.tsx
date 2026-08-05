import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { NavSidebar } from "../components/NavSidebar";
import { Header } from "../components/Header";
import { useAuth } from "../App";

type Theme = "dark" | "light" | "system";

function applyTheme(theme: Theme) {
  const resolved = theme === "system" ? (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : theme;
  document.documentElement.setAttribute("data-theme", resolved);
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      className={`toggle ${on ? "on" : ""}`}
      onClick={() => onChange(!on)}
      role="switch"
      aria-checked={on}
    >
      <span className="knob" />
    </button>
  );
}

export function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [theme, setTheme] = useState<Theme>("dark");
  const [sendOnEnter, setSendOnEnter] = useState(() => localStorage.getItem("aw_send_on_enter") !== "false");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const logoutNow = () => {
    logout();
    navigate("/login");
  };

  const toggleSendOnEnter = (v: boolean) => {
    setSendOnEnter(v);
    localStorage.setItem("aw_send_on_enter", String(v));
  };

  const clearConversations = async () => {
    if (!window.confirm("Delete all your conversations? Projects and uploaded files are kept.")) return;
    setBusy(true);
    try {
      const res = await api.delete<{ deleted: number }>("/auth/me/conversations");
      setNotice(`Deleted ${res.deleted} conversation${res.deleted === 1 ? "" : "s"}.`);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Failed to clear conversations");
    } finally {
      setBusy(false);
    }
  };

  const deleteAccount = async () => {
    if (!window.confirm("Delete your account and ALL data? This cannot be undone.")) return;
    setBusy(true);
    try {
      await api.delete("/auth/me");
      logout();
      navigate("/login");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Failed to delete account");
      setBusy(false);
    }
  };

  return (
    <div className="shell">
      <NavSidebar active="settings" userName={user?.name ?? ""} userEmail={user?.email ?? ""} onLogout={logoutNow} />
      <div className="main-area">
        <Header
          title="Settings"
          breadcrumb="Account"
          userName={user?.name ?? ""}
          userEmail={user?.email ?? ""}
          onToggleSidebar={() => {}}
          onLogout={logoutNow}
        />
        <div className="content">
          <div className="settings-layout">
            {notice && (
              <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "10px 14px", fontSize: 13 }}>
                {notice}
              </div>
            )}

            <section>
              <div className="settings-section-title">General</div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Theme</div>
                  <div className="settings-row-desc">Appearance across the app</div>
                </div>
                <div className="settings-control">
                  <select className="select" value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                    <option value="system">System</option>
                  </select>
                </div>
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Send on Enter</div>
                  <div className="settings-row-desc">Enter sends, Shift+Enter for a new line</div>
                </div>
                <Toggle on={sendOnEnter} onChange={toggleSendOnEnter} />
              </div>
            </section>

            <section>
              <div className="settings-section-title danger">Danger Zone</div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Log out</div>
                  <div className="settings-row-desc">End this session on this device</div>
                </div>
                <button className="btn-secondary" onClick={logoutNow}>
                  Log Out
                </button>
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Clear all conversations</div>
                  <div className="settings-row-desc">Delete every thread. Projects and files are kept.</div>
                </div>
                <button className="btn-secondary" onClick={() => void clearConversations()} disabled={busy}>
                  Clear All
                </button>
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Delete account</div>
                  <div className="settings-row-desc">Permanently delete your account and all data.</div>
                </div>
                <button className="btn-danger" onClick={() => void deleteAccount()} disabled={busy}>
                  Delete
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
