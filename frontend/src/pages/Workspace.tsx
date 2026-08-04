import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Conversation, ConversationDetail, Message, Project, ProjectFile } from "../lib/types";
import { Sidebar } from "../components/Sidebar";
import { Header } from "../components/Header";
import { ChatMessage } from "../components/ChatMessage";
import { Composer } from "../components/Composer";
import { Icon } from "../components/Icon";
import { useAuth } from "../App";

export function Workspace() {
  const { projectId, conversationId } = useParams<{ projectId: string; conversationId: string }>();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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
  }, [detail?.messages.length]);

  const logoutNow = () => {
    logout();
    navigate("/login");
  };

  const newChat = async () => {
    if (!projectId) return;
    const c = await api.post<Conversation>(`/projects/${projectId}/conversations`, {});
    await loadConversations();
    navigate(`/app/projects/${projectId}/conversations/${c.id}`, { replace: true });
  };

  const selectConversation = (id: string) => {
    navigate(`/app/projects/${projectId}/conversations/${id}`);
  };

  const togglePin = async (c: Conversation) => {
    await api.patch<Conversation>(`/projects/${projectId}/conversations/${c.id}`, { pinned: !c.pinned });
    await loadConversations();
  };

  const deleteConversation = async (c: Conversation) => {
    if (!window.confirm(`Delete "${c.title || "Untitled chat"}"?`)) return;
    await api.delete(`/projects/${projectId}/conversations/${c.id}`);
    if (c.id === activeId) {
      navigate(`/app/projects/${projectId}`, { replace: true });
    }
    await loadConversations();
  };

  const changeModel = async (model: string) => {
    if (!project) return;
    const updated = await api.patch<Project>(`/projects/${project.id}`, { model });
    setProject(updated);
  };

  const sendMessage = async (text: string) => {
    if (!projectId) return;
    let cid = activeId;
    if (!cid) {
      const c = await api.post<Conversation>(`/projects/${projectId}/conversations`, {});
      cid = c.id;
      await loadConversations();
      navigate(`/app/projects/${projectId}/conversations/${c.id}`, { replace: true });
    }
    setSending(true);
    // optimistic user message
    const optimistic: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setDetail((d) => (d ? { ...d, messages: [...d.messages, optimistic] } : d));
    try {
      const reply = await api.post<Message>(`/projects/${projectId}/conversations/${cid}/chat`, { message: text });
      const d = await api.get<ConversationDetail>(`/projects/${projectId}/conversations/${cid}`);
      setDetail(d);
      if (!d.title) {
        await loadConversations();
      }
      void reply;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      const d = await api.get<ConversationDetail>(`/projects/${projectId}/conversations/${cid}`);
      setDetail(d);
    } finally {
      setSending(false);
    }
  };

  const attachFile = async (file: File) => {
    if (!projectId) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload<ProjectFile>(`/projects/${projectId}/files`, form);
      const fs = await api.get<ProjectFile[]>(`/projects/${projectId}/files`);
      setFiles(fs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const lastMessages = detail?.messages ?? [];

  return (
    <div className="shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        userName={user?.name ?? ""}
        userEmail={user?.email ?? ""}
        projectModel={project?.model ?? ""}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={() => void newChat()}
        onSelect={selectConversation}
        onTogglePin={(c) => void togglePin(c)}
        onDelete={(c) => void deleteConversation(c)}
        onModelChange={(m) => void changeModel(m)}
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

        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-scroll-inner">
            {!activeId && (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <Icon name="chat" size={48} />
                </div>
                <h3>{project?.name}</h3>
                <p>{project?.description || "Start a conversation with this agent."}</p>
              </div>
            )}
            {lastMessages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {sending && (
              <div className="assistant-msg">
                <div className="msg-avatar">AI</div>
                <div className="assistant-body">
                  <div className="thinking-block">
                    <div className="thinking-toggle">
                      <span className="pulse-dot" />
                      Thinking…
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {files.length > 0 && (
          <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 24px 10px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {files.map((f) => (
                <span key={f.id} className="file-chip" style={{ cursor: "default" }}>
                  <Icon name="paperclip" size={12} />
                  {f.original_filename}
                  <span style={{ color: "var(--fg-dim)" }}>
                    {f.chunk_count > 0 ? `· ${f.chunk_count} chunks indexed` : "· indexing…"}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}

        <Composer sending={sending} onSend={(t) => void sendMessage(t)} onAttach={(f) => void attachFile(f)} />
      </div>
    </div>
  );
}
