import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Preferences, Project } from "../lib/types";
import { groupByDay } from "../lib/time";
import { NavSidebar } from "../components/NavSidebar";
import { Header } from "../components/Header";
import { Icon } from "../components/Icon";
import { MODEL_CATALOG } from "../components/Sidebar";
import { useToast } from "../components/Toast";
import { useAuth } from "../App";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [prefs, setPrefs] = useState<Preferences>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== "undefined" && window.innerWidth >= 768);

  const load = useCallback(async () => {
    try {
      const [ps, prefsRes] = await Promise.all([
        api.get<Project[]>("/projects"),
        api.get<Preferences>("/auth/me/preferences"),
      ]);
      setProjects(ps);
      setPrefs(prefsRes);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to load projects", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const logoutNow = () => {
    logout();
    navigate("/login");
  };

  const confirmDeleteProject = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/projects/${deleteTarget.id}`);
      toast(`Deleted project "${deleteTarget.name}"`, "success");
      setDeleteTarget(null);
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to delete project", "error");
    } finally {
      setDeleteBusy(false);
    }
  };

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(query.toLowerCase())
  );
  const groups = groupByDay(filtered);

  return (
    <div className="shell">
      <NavSidebar
        active="projects"
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
          title="Projects"
          breadcrumb="All"
          userName={user?.name ?? ""}
          userEmail={user?.email ?? ""}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onLogout={logoutNow}
        />
        <div className="content">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <div className="search-box" style={{ width: 260 }}>
              <Icon name="search" size={14} />
              <input
                placeholder="Search projects..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div style={{ flex: 1 }} />
            <button className="create-btn" onClick={() => setCreateOpen(true)}>
              <Icon name="plus" size={14} />
              New Project
            </button>
          </div>

          {!loading && groups.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Icon name="folder" size={48} />
              </div>
              <h3>{query ? "No matching projects" : "No projects yet"}</h3>
              <p>{query ? "Try a different search." : "Create your first project to start chatting."}</p>
            </div>
          )}

          {groups.map(([label, items]) => (
            <div key={label}>
              <div className="section-label">{label}</div>
              <div className="project-grid">
                {items.map((p) => (
                  <ProjectCard
                    key={p.id}
                    project={p}
                    onOpen={() => navigate(`/app/projects/${p.id}`)}
                    onDelete={() => setDeleteTarget(p)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {createOpen && (
        <CreateProjectModal
          defaultModel={prefs.default_model || undefined}
          onClose={() => setCreateOpen(false)}
          onCreate={async (data) => {
            const p = await api.post<Project>("/projects", data);
            navigate(`/app/projects/${p.id}`);
          }}
        />
      )}

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete project</DialogTitle>
            <DialogDescription>
              Delete "{deleteTarget?.name}"? This permanently removes the project, all of its
              conversations, and uploaded files. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => void confirmDeleteProject()} disabled={deleteBusy}>
              {deleteBusy ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProjectCard({ project, onOpen, onDelete }: { project: Project; onOpen: () => void; onDelete: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const modelLabel = MODEL_CATALOG.find((m) => m.id === project.model)?.label ?? project.model;

  return (
    <div className="project-card" onClick={onOpen}>
      <div className="project-card-title">{project.name}</div>
      <div className="project-card-desc">{project.description || "No description"}</div>
      <div className="project-tags">
        <span className="project-tag">{modelLabel}</span>
      </div>
      <div className="project-meta">
        <span className="model-dot" />
        <span>{modelLabel}</span>
        <span>·</span>
        <span>{groupByDay([project])[0]?.[0] ?? ""}</span>
      </div>
      <div
        className="project-card-menu"
        title="Project options"
        onClick={(e) => {
          e.stopPropagation();
          setMenuOpen((v) => !v);
        }}
      >
        <Icon name="kebab" size={16} />
      </div>
      {menuOpen && (
        <div
          className="profile-dropdown"
          style={{ position: "absolute", top: 34, right: 8, bottom: "auto", left: "auto" }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="profile-dropdown-item danger"
            onClick={() => {
              setMenuOpen(false);
              onDelete();
            }}
          >
            <Icon name="trash" size={14} />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function CreateProjectModal({
  defaultModel,
  onClose,
  onCreate,
}: {
  defaultModel?: string;
  onClose: () => void;
  onCreate: (data: { name: string; description?: string; model?: string; system_prompt?: string }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [model, setModel] = useState(defaultModel || MODEL_CATALOG[0].id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setBusy(true);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        model,
        system_prompt: systemPrompt.trim() || undefined,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create project";
      setError(message);
      toast(message, "error");
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">New Project</div>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              className="form-input"
              placeholder="e.g. Support Bot"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <input
              className="form-input"
              placeholder="What does this agent do?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Model</label>
            <select className="select" style={{ width: "100%" }} value={model} onChange={(e) => setModel(e.target.value)}>
              {MODEL_CATALOG.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">System prompt</label>
            <textarea
              className="form-input"
              style={{ minHeight: 72, resize: "vertical" }}
              placeholder="Optional instructions for this agent…"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
            />
          </div>
          {error && <div className="error-msg visible">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="create-btn" type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
