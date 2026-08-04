import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "./Icon";
import { initials } from "./Sidebar";

interface HeaderProps {
  title: string;
  breadcrumb: string;
  userName: string;
  userEmail: string;
  onToggleSidebar: () => void;
  onLogout: () => void;
}

export function Header({ title, breadcrumb, userName, userEmail, onToggleSidebar, onLogout }: HeaderProps) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="header">
      <button className="icon-btn" onClick={onToggleSidebar} title="Toggle sidebar">
        <Icon name="sidebar" size={16} />
      </button>
      <span className="header-title">{title}</span>
      <div className="breadcrumb">
        <span className="link" onClick={() => navigate("/app")}>
          Projects
        </span>
        <Icon name="chevronRight" size={12} />
        <span>{breadcrumb}</span>
      </div>
      <div className="header-spacer" />
      <div style={{ position: "relative" }}>
        <button className="icon-btn" onClick={() => setMenuOpen((v) => !v)} title="Profile">
          <span className="avatar md">{initials(userName)}</span>
        </button>
        {menuOpen && (
          <div className="profile-dropdown" style={{ position: "absolute", top: 34, right: 0, bottom: "auto", left: "auto" }}>
            <div className="profile-dropdown-header">
              <div className="profile-dropdown-name">{userName || "You"}</div>
              <div className="profile-dropdown-email">{userEmail}</div>
            </div>
            <button
              className="profile-dropdown-item"
              onClick={() => {
                setMenuOpen(false);
                navigate("/app/settings");
              }}
            >
              <Icon name="settings" size={14} />
              Settings
            </button>
            <button
              className="profile-dropdown-item"
              onClick={() => {
                setMenuOpen(false);
                navigate("/app");
              }}
            >
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
    </header>
  );
}
