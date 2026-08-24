import { useNavigate } from "react-router-dom";
import type { Conversation, ModelOption } from "../lib/types";
import { groupByDay } from "../lib/time";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  MessageSquare,
  Pin,
  Trash2,
  Settings,
  FolderOpen,
  LogOut,
} from "lucide-react";
import { Logo } from "./Logo";

export const MODEL_CATALOG: ModelOption[] = [
  { id: "deepseek-v4-flash", label: "DeepSeek V4 Flash", description: "Fastest inference, best for code generation and analysis" },
  { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro", description: "Stronger reasoning for complex architecture decisions" },
  { id: "minimax-m3", label: "MiniMax M3", description: "Latest MiniMax flagship model" },
  { id: "minimax-m2.5", label: "MiniMax M2.5", description: "Balanced MiniMax model" },
  { id: "kimi-k3", label: "Kimi K3", description: "Latest Kimi flagship model" },
  { id: "kimi-k2.7-code", label: "Kimi K2.7 Code", description: "Code-focused Kimi model" },
  { id: "kimi-k2.6", label: "Kimi K2.6", description: "Strong general reasoning" },
  { id: "kimi-k2.5", label: "Kimi K2.5", description: "Balanced Kimi model" },
  { id: "glm-5.2", label: "GLM 5.2", description: "Latest GLM flagship model" },
  { id: "glm-5.1", label: "GLM 5.1", description: "Latest GLM model" },
  { id: "glm-5", label: "GLM 5", description: "Strong GLM reasoning model" },
  { id: "qwen3.8-max", label: "Qwen 3.8 Max", description: "Largest Qwen 3.8 model" },
  { id: "qwen3.7-max", label: "Qwen 3.7 Max", description: "Qwen 3.7 flagship" },
  { id: "qwen3.7-plus", label: "Qwen 3.7 Plus", description: "Strong Qwen 3.7 model" },
  { id: "qwen3.6-plus", label: "Qwen 3.6 Plus", description: "Balanced Qwen model" },
  { id: "qwen3.5-plus", label: "Qwen 3.5 Plus", description: "Efficient Qwen model" },
  { id: "mimo-v2.5-pro", label: "Mimo V2.5 Pro", description: "Latest Mimo pro model" },
  { id: "mimo-v2.5", label: "Mimo V2.5", description: "Latest Mimo model" },
  { id: "hy3", label: "HY3", description: "Hyperbolic 3 model" },
  { id: "mimo-v2.5-free", label: "MiMo-V2.5 Free", description: "Latest Mimo model, free via OpenCode Zen (fallback)" },
  { id: "hy3-free", label: "Hy3 Free", description: "Hyperbolic 3 model, free via OpenCode Zen (fallback)" },
  { id: "laguna-s-2.1-free", label: "Laguna S 2.1 Free", description: "Free via OpenCode Zen (fallback)" },
  { id: "nemotron-3-ultra-free", label: "Nemotron 3 Ultra Free", description: "NVIDIA flagship, free via OpenCode Zen (fallback)" },
  { id: "nemotron-3.5-lightning-free", label: "Nemotron 3.5 Lightning Free", description: "NVIDIA lightning model, free via OpenCode Zen (fallback)" },
];

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  userName: string;
  userEmail: string;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onTogglePin: (c: Conversation) => void;
  onDelete: (c: Conversation) => void;
  onLogout: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  userName,
  userEmail,
  open,
  onClose,
  onNewChat,
  onSelect,
  onTogglePin,
  onDelete,
  onLogout,
}: SidebarProps) {
  const navigate = useNavigate();
  const groups = groupByDay(conversations);

  return (
    <>
      <aside className={`sidebar ${open ? "open" : "collapsed"}`}>
        <div className="sidebar-header sidebar-header-stack">
          <div className="sidebar-brand-row">
            <Logo size={24} />
            <span className="sidebar-brand-name">openagent</span>
          </div>
          <Button variant="secondary" className="new-chat-btn gap-1.5 w-full justify-start" onClick={onNewChat} title="Start a new conversation">
            <Plus className="h-3.5 w-3.5" />
            New Chat
          </Button>
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
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  <span className="thread-title">{c.title || "Untitled chat"}</span>
                  <span className="thread-actions">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 p-0 thread-action-btn"
                      title={c.pinned ? "Unpin" : "Pin"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onTogglePin(c);
                      }}
                    >
                      <Pin className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 p-0 thread-action-btn text-destructive hover:text-destructive"
                      title="Delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(c);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="user-profile w-full justify-start gap-2 h-auto py-2 px-3">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="text-[10px] bg-accent/20 text-accent">{initials(userName)}</AvatarFallback>
                </Avatar>
                <span className="flex-1 truncate text-left">{userName || userEmail}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="text-sm font-medium">{userName || "You"}</div>
                <div className="text-xs text-muted-foreground">{userEmail}</div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate("/app/settings")}>
                <Settings className="h-4 w-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate("/app")}>
                <FolderOpen className="h-4 w-4" />
                Projects
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onLogout} className="text-destructive focus:text-destructive">
                <LogOut className="h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
