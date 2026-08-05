import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getToken } from "../lib/api";
import type { Conversation, ConversationDetail, Message, Project, ProjectFile } from "../lib/types";
import { Sidebar } from "../components/Sidebar";
import { Header } from "../components/Header";
import { Logo } from "../components/Logo";
import { ChatMessage } from "../components/ChatMessage";
import { Composer } from "../components/Composer";
import { CanvasPane, type CanvasArtifact } from "../components/CanvasPane";
import { StreamingMessage, type StreamingDraft, type ToolCallUI } from "../components/StreamingMessage";
import { ThinkingPhrases } from "../components/ThinkingPhrases";
import { useAuth } from "../App";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Paperclip } from "lucide-react";
import { extractArtifacts, isSubstantialArtifact, toCanvasArtifact } from "../lib/artifacts";

export function Workspace() {
  const { projectId, conversationId } = useParams<{ projectId: string; conversationId: string }>();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== "undefined" && window.innerWidth >= 768);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState<StreamingDraft | null>(null);
  const [artifactList, setArtifactList] = useState<CanvasArtifact[]>([]);
  const [artifactActive, setArtifactActive] = useState<string | undefined>(undefined);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [attachments, setAttachments] = useState<{ file: File; name: string }[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoOpenedRef = useRef(false);

  const openCanvas = (a: CanvasArtifact) => {
    setArtifactList((prev) => {
      const exists = prev.some((x) => (x.path ?? x.lang) === (a.path ?? a.lang));
      return exists ? prev : [...prev, a];
    });
    setArtifactActive(a.path ?? a.lang);
    setCanvasOpen(true);
  };

  // Auto-open the canvas split-view as soon as a substantial fenced code
  // block (HTML/SVG/previewable or filename-hinted) streams in.
  useEffect(() => {
    if (!draft?.content) return;
    const blocks = extractArtifacts(draft.content);
    const substantial = blocks.filter(isSubstantialArtifact);
    if (substantial.length > 0 && !autoOpenedRef.current) {
      autoOpenedRef.current = true;
      setArtifactList(substantial.map(toCanvasArtifact));
      setArtifactActive(substantial[0].name);
      setCanvasOpen(true);
    }
  }, [draft?.content]);

  const activeId = conversationId ?? null;

  const loadConversations = useCallback(async () => {
    if (!projectId) return;
    const convs = await api.get<Conversation[]>(`/projects/${projectId}/conversations`);
    setConversations(convs);
  }, [projectId]);

  const loadDetail = useCallback(async () => {
    if (!projectId || !conversationId) return;
    const d = await api.get<ConversationDetail>(`/projects/${projectId}/conversations/${conversationId}`);
    setDetail(d);
  }, [projectId, conversationId]);

  useEffect(() => {
    if (!projectId) return;
    Promise.all([api.get<Project>(`/projects/${projectId}`), api.get<ProjectFile[]>(`/projects/${projectId}/files`)])
      .then(([p, fs]) => {
        setProject(p);
        setFiles(fs);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load project"))
      .then(() => loadConversations());
  }, [projectId, loadConversations]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [detail?.messages.length, draft?.content.length, draft?.thinking.length]);

  const logoutNow = () => {
    logout();
    navigate("/login");
  };

  const newChat = async () => {
    if (!projectId) return;
    const c = await api.post<Conversation>(`/projects/${projectId}/conversations`, {});
    await loadConversations();
    if (window.innerWidth < 768) setSidebarOpen(false);
    navigate(`/app/projects/${projectId}/conversations/${c.id}`, { replace: true });
  };

  const selectConversation = (id: string) => {
    if (window.innerWidth < 768) setSidebarOpen(false);
    navigate(`/app/projects/${projectId}/conversations/${id}`);
  };

  const togglePin = async (c: Conversation) => {
    await api.patch<Conversation>(`/projects/${projectId}/conversations/${c.id}`, { pinned: !c.pinned });
    await loadConversations();
  };

  const deleteConversation = (c: Conversation) => {
    setDeleteTarget(c);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await api.delete(`/projects/${projectId}/conversations/${deleteTarget.id}`);
    if (deleteTarget.id === activeId) {
      navigate(`/app/projects/${projectId}`, { replace: true });
    }
    setDeleteTarget(null);
    await loadConversations();
  };

  const changeModel = async (model: string) => {
    if (!project) return;
    const updated = await api.patch<Project>(`/projects/${project.id}`, { model });
    setProject(updated);
  };

  const sendMessage = async (text: string, reasoningEffort: "standard" | "max" = "standard") => {
    if (!projectId) return;
    let cid = activeId;
    if (!cid) {
      const c = await api.post<Conversation>(`/projects/${projectId}/conversations`, {});
      cid = c.id;
      await loadConversations();
      navigate(`/app/projects/${projectId}/conversations/${c.id}`, { replace: true });
    }
    setSending(true);
    setError(null);
    autoOpenedRef.current = false;
    const currentAttachments = [...attachments];
    setAttachments([]);
    // optimistic user message
    const optimistic: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setDetail((d) => (d ? { ...d, messages: [...d.messages, optimistic] } : d));
    setDraft({ thinking: "", content: "", tools: [], provider: "primary", model: "" });
    try {
      // Encode attachments as base64 for message-scoped context
      const encoded = await Promise.all(
        currentAttachments.map(async (a) => {
          const buf = await a.file.arrayBuffer();
          const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
          return { filename: a.name, content_b64: b64 };
        })
      );
      await streamChat(projectId, cid, text, encoded, reasoningEffort);
      const d = await api.get<ConversationDetail>(`/projects/${projectId}/conversations/${cid}`);
      setDetail(d);
      if (d.title) {
        await loadConversations();
      }
    } catch (err) {
      // Keep the pending attachments so the user can retry
      setAttachments(currentAttachments);
      setError(err instanceof Error ? err.message : "Chat failed");
      const d = await api.get<ConversationDetail>(`/projects/${projectId}/conversations/${cid}`);
      setDetail(d);
    } finally {
      setSending(false);
      setDraft(null);
    }
  };

  const streamChat = async (pid: string, cid: string, text: string, attachments?: { filename: string; content_b64: string }[], reasoningEffort?: "standard" | "max") => {
    const res = await fetch(`/projects/${pid}/conversations/${cid}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken() ?? ""}`,
      },
      body: JSON.stringify({ message: text, attachments: attachments?.length ? attachments : undefined, reasoning_effort: reasoningEffort }),
    });
    if (!res.ok) {
      let message = `Chat failed (${res.status})`;
      try {
        const body = await res.json();
        if (body && typeof body === "object" && "error" in body) message = String((body as { error: unknown }).error);
      } catch {
        /* non-JSON error body */
      }
      if (res.status === 401) window.dispatchEvent(new Event("aw:unauthorized"));
      throw new Error(message);
    }
    if (!res.body) throw new Error("Chat stream unavailable");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const raw of lines) {
        const line = raw.trim();
        if (!line.startsWith("data:")) continue;
        let ev: { event?: string; delta?: string; error?: string; id?: string; name?: string; arguments?: string; provider?: string; model?: string };
        try {
          ev = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }
        switch (ev.event) {
          case "thinking":
            setDraft((d) => (d ? { ...d, thinking: d.thinking + (ev.delta ?? "") } : d));
            break;
          case "content":
            setDraft((d) => (d ? { ...d, content: d.content + (ev.delta ?? "") } : d));
            break;
          case "tool": {
            const tool: ToolCallUI = { id: ev.id ?? "", name: ev.name ?? "tool", arguments: ev.arguments ?? "" };
            setDraft((d) =>
              d
                ? {
                    ...d,
                    tools: [...d.tools.filter((t) => t.id !== tool.id), tool],
                  }
                : d
            );
            break;
          }
          case "provider":
            setDraft((d) => (d ? { ...d, provider: ev.provider ?? "primary", model: ev.model ?? "" } : d));
            break;
          case "error":
            throw new Error(ev.error ?? "The model service is unavailable, please try again");
        }
      }
    }
  };

  const lastMessages = detail?.messages ?? [];

  return (
    <>
      <div className="shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        userName={user?.name ?? ""}
        userEmail={user?.email ?? ""}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={() => void newChat()}
        onSelect={selectConversation}
        onTogglePin={(c) => void togglePin(c)}
        onDelete={(c) => void deleteConversation(c)}
        onLogout={logoutNow}
      />
      <div className="main-area">
        <Header
          title={project?.name ?? "Project"}
          breadcrumb={detail?.title ?? "Main Thread"}
          userName={user?.name ?? ""}
          userEmail={user?.email ?? ""}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onLogout={logoutNow}
        />

        {error && (
          <div style={{ padding: "8px 16px", background: "rgba(251,113,133,0.1)", color: "var(--accent-rose)", fontSize: 13 }}>
            {error}
          </div>
        )}

        <div className="content-split">
          <div className="chat-pane">
            <div className="chat-scroll" ref={scrollRef}>
              <div className="chat-scroll-inner">
                {(!activeId || lastMessages.length === 0) && !draft && !sending && (
                  <div className="empty-state">
                    <div className="empty-state-icon">
                      <Logo size={48} />
                    </div>
                    <h3>{project?.name}</h3>
                    <p>
                      {activeId
                        ? "No messages yet. Send your first message to start the conversation."
                        : project?.description || "Start a new conversation or select one from the sidebar."}
                    </p>
                  </div>
                )}
                {lastMessages.map((m) => (
                  <ChatMessage key={m.id} message={m} onOpenCanvas={openCanvas} />
                ))}
                {draft && <StreamingMessage draft={draft} onOpenCanvas={openCanvas} />}
                {sending && !draft && (
                  <div className="assistant-msg">
                    <div className="msg-avatar">AI</div>
                    <div className="assistant-body">
                      <div className="thinking-block">
                        <div className="thinking-toggle">
                          <span className="spin-logo">
                            <Logo size={14} />
                          </span>
                          <ThinkingPhrases />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {files.length > 0 && (
              <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 24px 10px" }}>
                <div style={{ color: "var(--fg-dim)", fontSize: 12, marginBottom: 6 }}>
                  Project files · knowledge base for this agent
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {files.map((f) => (
                    <Badge key={f.id} variant="secondary" className="file-chip gap-1.5 font-normal cursor-default">
                      <Paperclip className="h-3 w-3 shrink-0" />
                      {f.original_filename}
                      <span className="text-muted-foreground">
                        {f.chunk_count > 0 ? `· ${f.chunk_count} chunks indexed` : "· indexing…"}
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <Composer
              sending={sending}
              projectModel={project?.model ?? ""}
              attachments={attachments}
              onRemoveAttachment={(i) => setAttachments((prev) => prev.filter((_, idx) => idx !== i))}
              onSend={(t, effort) => void sendMessage(t, effort)}
              onAttach={(files) => {
                const newAttachments = Array.from(files).map((f) => ({ file: f, name: f.name }));
                setAttachments((prev) => [...prev, ...newAttachments]);
              }}
              onModelChange={(m) => void changeModel(m)}
            />
          </div>

          {canvasOpen && artifactList.length > 0 && (
            <CanvasPane
              artifacts={artifactList}
              activeName={artifactActive}
              onClose={() => setCanvasOpen(false)}
            />
          )}
        </div>
      </div>
      </div>
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation</DialogTitle>
            <DialogDescription>
              Delete "{deleteTarget?.title || "Untitled chat"}"? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => void confirmDelete()}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
