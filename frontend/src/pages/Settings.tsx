import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { NavSidebar } from "../components/NavSidebar";
import { Header } from "../components/Header";
import { useAuth } from "../App";
import { useToast } from "../components/Toast";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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
      title={on ? "Turn off" : "Turn on"}
    >
      <span className="knob" />
    </button>
  );
}

export function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [theme, setTheme] = useState<Theme>("dark");
  const [sendOnEnter, setSendOnEnter] = useState(() => localStorage.getItem("aw_send_on_enter") !== "false");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== "undefined" && window.innerWidth >= 768);

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
    setBusy(true);
    try {
      const res = await api.delete<{ deleted: number }>("/auth/me/conversations");
      setNotice(`Deleted ${res.deleted} conversation${res.deleted === 1 ? "" : "s"}.`);
      toast(`Deleted ${res.deleted} conversation${res.deleted === 1 ? "" : "s"}`, "success");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to clear conversations";
      setNotice(message);
      toast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const deleteAccount = async () => {
    setBusy(true);
    try {
      await api.delete("/auth/me");
      logout();
      navigate("/login");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete account";
      setNotice(message);
      toast(message, "error");
      setBusy(false);
    }
  };

  return (
    <div className="shell">
      <NavSidebar
        active="settings"
        userName={user?.name ?? ""}
        userEmail={user?.email ?? ""}
        open={sidebarOpen}
        onNavigate={() => {
          if (window.innerWidth < 768) setSidebarOpen(false);
        }}
        onLogout={logoutNow}
      />
      <div className="main-area">
        <Header
          title="Settings"
          breadcrumb="Account"
          userName={user?.name ?? ""}
          userEmail={user?.email ?? ""}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
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
                <button className="btn-secondary" onClick={() => setConfirmClear(true)} disabled={busy}>
                  Clear All
                </button>
              </div>
              <div className="settings-row">
                <div>
                  <div className="settings-row-label">Delete account</div>
                  <div className="settings-row-desc">Permanently delete your account and all data.</div>
                </div>
                <button className="btn-danger" onClick={() => setConfirmDelete(true)} disabled={busy}>
                  Delete
                </button>
              </div>
            </section>

            <Dialog open={confirmClear} onOpenChange={(open) => !open && setConfirmClear(false)}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Clear all conversations</DialogTitle>
                  <DialogDescription>
                    Delete every conversation in your account? Projects and uploaded files are kept.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setConfirmClear(false)}>Cancel</Button>
                  <Button variant="destructive" onClick={() => { setConfirmClear(false); void clearConversations(); }} disabled={busy}>
                    Clear All
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={confirmDelete} onOpenChange={(open) => !open && setConfirmDelete(false)}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete account</DialogTitle>
                  <DialogDescription>
                    Permanently delete your account and ALL data? This cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                  <Button variant="destructive" onClick={() => { setConfirmDelete(false); void deleteAccount(); }} disabled={busy}>
                    Delete
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>
    </div>
  );
}
