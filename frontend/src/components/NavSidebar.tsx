import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "./Icon";
import { Logo } from "./Logo";
import { initials } from "./Sidebar";

interface NavSidebarProps {
  active: "projects" | "settings";
  userName: string;
  userEmail: string;
  open: boolean;
  onNavigate?: () => void;
  onLogout: () => void;
}

export function NavSidebar({ active, userName, userEmail, open, onNavigate, onLogout }: NavSidebarProps) {
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);

  const go = (path: string) => {
    onNavigate?.();
    navigate(path);
  };

  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="sidebar-header">
        <Logo size={28} />
        <span style={{ fontSize: 14, fontWeight: 600 }}>openagent</span>
      </div>

      <nav className="sidebar-threads">
        <button
          className={`thread-item ${active === "projects" ? "active" : ""}`}
          onClick={() => go("/app")}
        >
          <Icon name="folder" size={14} />
          <span className="thread-title">Projects</span>
        </button>
        <button
          className={`thread-item ${active === "settings" ? "active" : ""}`}
          onClick={() => go("/app/settings")}
        >
          <Icon name="settings" size={14} />
          <span className="thread-title">Settings</span>
        </button>
      </nav>

      <div className="sidebar-footer" style={{ position: "relative" }}>
        <button
          className="user-profile"
          onClick={() => setProfileOpen((v) => !v)}
        >
          <span className="avatar sm">{initials(userName)}</span>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {userName || userEmail}
          </span>
        </button>

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
            <div className="profile-divider" />
            <button className="profile-dropdown-item danger" onClick={onLogout}>
              <Icon name="logout" size={14} />
              Log out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
