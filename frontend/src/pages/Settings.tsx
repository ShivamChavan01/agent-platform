import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Preferences, Usage } from "../lib/types";
import { NavSidebar } from "../components/NavSidebar";
import { Header } from "../components/Header";
import { MODEL_CATALOG } from "../components/Sidebar";
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

const API_KEY_ROWS = [
  { name: "DeepSeek", masked: "ds-****…****8f2a" },
  { name: "OpenAI", masked: "sk-****…****3b7d" },
  { name: "Anthropic", masked: "sk-ant-****…****9c1e" },
];

export function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [theme, setTheme] = useState<Theme>("dark");
  const [language, setLanguage] = useState("English");
  const [sendOnEnter, setSendOnEnter] = useState(() => localStorage.getItem("aw_send_on_enter") !== "false");
  const [spellCheck, setSpellCheck] = useState(true);
  const [autoSave, setAutoSave] = useState(true);
  const [canvasApply, setCanvasApply] = useState(true);
  const [showThinking, setShowThinking] = useState(true);
  const [prefs, setPrefs] = useState<Preferences>({});
  const [usage, setUsage] = useState<Usage | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [p, u] = await Promise.all([
      api.get<Preferences>("/auth/me/preferences"),
      api.get<Usage>("/auth/me/usage?window_hours=24"),
    ]);
    setPrefs(p);
    setUsage(u);
  }, []);

  useEffect(() => {
    void load();
    applyTheme(theme);
  }, [theme, load]);

  const logoutNow = () => {
    logout();
    navigate("/login");
  };

  const setPref = async (key: keyof Preferences, value: string | number | null) => {
    await api.patch<Preferences>("/auth/me/preferences", { [key]: value });
    const p = await api.get<Preferences>("/auth/me/preferences");
    setPrefs(p);
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
                  <div className="settings-row-desc">Appearance across the workspace</div>
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
                  <div className="settings-row-label">Language</div>
                  <div className="settings-row-desc">Interface language</div>
                </div>
                <div className="settings-control">
                  <select className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
                    <option>English</option>
                    <option>Hindi</option>
                    <option>Japanese</option>
                    <option>Chinese</option>
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
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Spell check</div>
                  <div className="settings-row-desc">Spell check in the composer</div>
                </div>
                <Toggle on={spellCheck} onChange={setSpellCheck} />
              </div>
            </section>

            <section>
              <div className="settings-section-title">Usage</div>
              <div style={{ fontSize: 12, color: "var(--fg-dim)" }}>Token usage over the last {usage?.window_hours ?? 24} hours</div>
              <div className="usage-grid">
                <div className="usage-card">
                  <div className="usage-card-value">{usage?.requests ?? 0}</div>
                  <div className="usage-card-label">Requests</div>
                </div>
                <div className="usage-card">
                  <div className="usage-card-value">{usage?.total_tokens ?? 0}</div>
                  <div className="usage-card-label">Total tokens</div>
                </div>
                <div className="usage-card">
                  <div className="usage-card-value">{usage?.prompt_tokens ?? 0}</div>
                  <div className="usage-card-label">Prompt tokens</div>
                </div>
                <div className="usage-card">
                  <div className="usage-card-value">{usage?.completion_tokens ?? 0}</div>
                  <div className="usage-card-label">Completion tokens</div>
                </div>
              </div>
            </section>

            <section>
              <div className="settings-section-title">Default Model</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
                {MODEL_CATALOG.map((m) => {
                  const selected = (prefs.default_model ?? MODEL_CATALOG[0].id) === m.id;
                  return (
                    <button
                      key={m.id}
                      className={`model-card ${selected ? "selected" : ""}`}
                      onClick={() => void setPref("default_model", m.id)}
                    >
                      <span className="model-radio" />
                      <span style={{ flex: 1 }}>
                        <span className="model-card-name">
                          {m.label}
                          {selected && <span className="model-badge">Default</span>}
                        </span>
                        <span className="model-card-desc" style={{ display: "block" }}>
                          {m.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>

            <section>
              <div className="settings-section-title">Workspace</div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Auto-save</div>
                  <div className="settings-row-desc">Automatically save your work</div>
                </div>
                <Toggle on={autoSave} onChange={setAutoSave} />
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Canvas auto-apply</div>
                  <div className="settings-row-desc">Apply generated changes to the canvas</div>
                </div>
                <Toggle on={canvasApply} onChange={setCanvasApply} />
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Show thinking blocks</div>
                  <div className="settings-row-desc">Display reasoning steps in chat</div>
                </div>
                <Toggle on={showThinking} onChange={setShowThinking} />
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Context window</div>
                  <div className="settings-row-desc">Token context for your conversations</div>
                </div>
                <div className="settings-control">
                  <select
                    className="select"
                    value={String(prefs.context_window ?? 16)}
                    onChange={(e) => void setPref("context_window", Number(e.target.value))}
                  >
                    <option value="4">4K</option>
                    <option value="16">16K</option>
                    <option value="32">32K</option>
                    <option value="128">128K</option>
                  </select>
                </div>
              </div>
            </section>

            <section>
              <div className="settings-section-title">API Keys</div>
              <div style={{ fontSize: 12, color: "var(--fg-dim)", padding: "8px 0" }}>
                Keys are managed on the shared workspace — rotating them here is disabled.
              </div>
              {API_KEY_ROWS.map((row) => (
                <div className="api-key-row" key={row.name}>
                  <span className="api-key-name">{row.name}</span>
                  <span className="api-key-masked">{row.masked}</span>
                  <button className="btn-secondary" disabled title="Disabled">
                    Rotate
                  </button>
                </div>
              ))}
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
