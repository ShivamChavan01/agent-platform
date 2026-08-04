import { useNavigate } from "react-router-dom";
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
import { initials } from "./Sidebar";
import { PanelLeft, ChevronRight, Settings, FolderOpen, LogOut } from "lucide-react";

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

  return (
    <header className="header">
      <Button type="button" variant="ghost" size="icon" onClick={onToggleSidebar} title="Toggle sidebar">
        <PanelLeft className="h-4 w-4" />
      </Button>
      <span className="header-title">{title}</span>
      <div className="breadcrumb">
        <span className="link" onClick={() => navigate("/app")}>
          Projects
        </span>
        <ChevronRight className="h-3 w-3" />
        <span>{breadcrumb}</span>
      </div>
      <div className="header-spacer" />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" title="Profile">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="text-[11px] bg-accent/20 text-accent">{initials(userName)}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
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
    </header>
  );
}
