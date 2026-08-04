import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Conversation, ModelOption } from "../lib/types";
import { groupByDay } from "../lib/time";
import { Icon } from "./Icon";

export const MODEL_CATALOG: ModelOption[] = [
  {
    id: "deepseek/deepseek-v4-flash",
    label: "DeepSeek V4 Flash",
    description: "Fastest inference, best for code generation and analysis",
  },
  {
    id: "deepseek/deepseek-r1",
    label: "DeepSeek R1",
    description: "Strong reasoning for complex architecture decisions",
  },
  {
    id: "anthropic/claude-3.5-sonnet",
    label: "Claude 3.5 Sonnet",
    description: "Best reasoning, ideal for complex architecture decisions",
  },
  {
    id: "openai/gpt-4o",
    label: "GPT-4o",
    description: "Versatile model with strong multimodal capabilities",
  },
  {
    id: "google/gemini-2.0-pro",
    label: "Gemini 2.0 Pro",
    description: "Strong at long context and structured data tasks",
  },
];

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  userName: string;
  userEmail: string;
  projectModel: string;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onTogglePin: (c: Conversation) => void;
  onDelete: (c: Conversation) => void;
  onModelChange: (model: string) => void;
  onLogout: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  userName,
  userEmail,
  projectModel,
  open,
  onClose,
  onNewChat,
  onSelect,
  onTogglePin,
  onDelete,
  onModelChange,
  onLogout,
}: SidebarProps) {
  const [profileOpen, setProfileOpen] = useState(false);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const navigate = useNavigate();

  const groups = groupByDay(conversations);

  return (
    <>
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={onNewChat}>
            <Icon name="plus" size={14} />
            New Chat
          </button>
        </div>

        <nav className="sidebar-threads">
          {groups.length === 0 && (
            <div className="thread-group-label" style={{ padding: "12px 10px" }}>
              No conversations yet
            </div>
          )}
          {groups.map(([label, items]) => (
            <div key={label}>
              <div className="thread-group-label">{label}</div>
              {items.map((c) => (
                <div
                  key={c.id}
                  className={`thread-item ${c.id === activeId ? "active" : ""}`}
                  onClick={() => onSelect(c.id)}
                >
                  <Icon name="chat" size={14} />
                  <span className="thread-title">{c.title || "Untitled chat"}</span>
                  <span className="thread-actions">
                    <button
                      className="thread-action-btn"
                      title={c.pinned ? "Unpin" : "Pin"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onTogglePin(c);
                      }}
                    >
                      <Icon name="pin" size={12} />
                    </button>
                    <button
                      className="thread-action-btn danger"
                      title="Delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(c);
                      }}
                    >
                      <Icon name="trash" size={12} />
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer" style={{ position: "relative" }}>
          <button
            className="model-selector"
            onClick={() => {
              setModelMenuOpen((v) => !v);
              setProfileOpen(false);
            }}
          >
            <span className="model-dot" />
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {MODEL_CATALOG.find((m) => m.id === projectModel)?.label ?? projectModel}
            </span>
            <Icon name="chevronDown" size={14} />
          </button>
          <button
            className="user-profile"
            onClick={() => {
              setProfileOpen((v) => !v);
              setModelMenuOpen(false);
            }}
          >
            <span className="avatar sm">{initials(userName)}</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {userName || userEmail}
            </span>
          </button>

          {modelMenuOpen && (
            <div className="profile-dropdown" style={{ bottom: 110 }}>
              {MODEL_CATALOG.map((m) => (
                <button
                  key={m.id}
                  className="profile-dropdown-item"
                  onClick={() => {
                    onModelChange(m.id);
                    setModelMenuOpen(false);
                  }}
                >
                  {m.id === projectModel && <Icon name="check" size={14} />}
                  <span style={{ flex: 1 }}>{m.label}</span>
                </button>
              ))}
            </div>
          )}

          {profileOpen && (
            <div className="profile-dropdown">
              <div className="profile-dropdown-header">
                <div className="profile-dropdown-name">{userName || "You"}</div>
                <div className="profile-dropdown-email">{userEmail}</div>
              </div>
              <button className="profile-dropdown-item" onClick={() => navigate("/app/settings")}>
                <Icon name="settings" size={14} />
                Settings
              </button>
              <button className="profile-dropdown-item" onClick={() => navigate("/app")}>
                <Icon name="folder" size={14} />
                Projects
              </button>
              <div className="profile-divider" />
              <button className="profile-dropdown-item danger" onClick={onLogout}>
                <Icon name="logout" size={14} />
                Log out
              </button>
            </div>
          )}
        </div>
      </aside>
      {open && <div className="sidebar-overlay show" onClick={onClose} />}
    </>
  );
}

function initials(name: string): string {
  if (!name) return "?";
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export { initials };
