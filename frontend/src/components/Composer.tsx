import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Paperclip, Send, X, Check, ChevronDown, Zap } from "lucide-react";
import { MODEL_CATALOG } from "./Sidebar";

interface ComposerProps {
  sending: boolean;
  projectModel: string;
  attachments: { file: File; name: string }[];
  onRemoveAttachment: (index: number) => void;
  onSend: (text: string, reasoningEffort: "standard" | "max") => void;
  onAttach: (files: FileList) => void;
  onModelChange: (model: string) => void;
}

export function Composer({ sending, projectModel, attachments, onRemoveAttachment, onSend, onAttach, onModelChange }: ComposerProps) {
  const [text, setText] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState<"standard" | "max">("standard");
  const sendOnEnter = () => localStorage.getItem("aw_send_on_enter") !== "false";
  const fileRef = useRef<HTMLInputElement>(null);

  const modelLabel = MODEL_CATALOG.find((m) => m.id === projectModel)?.label ?? projectModel;

  const submit = () => {
    const value = text.trim();
    if (!value || sending) return;
    setText("");
    onSend(value, reasoningEffort);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && sendOnEnter()) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer-wrap">
      <div className="input-area">
        {attachments.length > 0 && (
          <div className="composer-attachments">
            {attachments.map((a, i) => (
              <Badge key={i} variant="secondary" className="composer-attachment gap-1.5 pr-1.5">
                <Paperclip className="h-3 w-3 shrink-0" />
                <span className="composer-attachment-name">{a.name}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 p-0 hover:bg-transparent hover:text-accent-rose shrink-0"
                  title="Remove attachment"
                  aria-label="Remove attachment"
                  onClick={() => onRemoveAttachment(i)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </Badge>
            ))}
          </div>
        )}
        <div className="input-box">
          <Textarea
            className="composer-textarea border-0 bg-transparent focus-visible:ring-0 shadow-none resize-none"
            rows={1}
            placeholder="Message openagent..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
            }}
          />
          <div className="composer-tools">
            <Button
              variant="ghost"
              size="sm"
              className="composer-btn gap-1.5"
              title="Attach files"
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </Button>
            <input
              ref={fileRef}
              type="file"
              hidden
              multiple
              accept=".txt,.md,.markdown,.rst,.csv,.json,.log,.pdf,.docx,.py,.js,.ts,.tsx,.jsx,.html,.css,.xml,.yaml,.yml,.toml,.ini,.cfg,.sql,.sh,.go,.rs,.rb,.c,.h,.cpp,.hpp,.java,.kt,.swift"
              title=".txt/.md/.csv/.json/code files, .pdf, .docx (max 10MB each)"
              onChange={(e) => {
                if (e.target.files?.length) onAttach(e.target.files);
                e.target.value = "";
              }}
            />
            <Button
              variant="ghost"
              size="sm"
              className={`composer-btn ${reasoningEffort === "max" ? "active" : ""}`}
              title={
                reasoningEffort === "max"
                  ? "Max reasoning: deeper, slower thinking"
                  : "Standard reasoning"
              }
              onClick={() =>
                setReasoningEffort((e) => (e === "standard" ? "max" : "standard"))
              }
            >
              <Zap className="h-3.5 w-3.5" />
              {reasoningEffort === "max" ? "Max" : "Standard"}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="model-pill gap-1"
                  title="Select model"
                >
                  <span className="model-dot" />
                  <span className="model-pill-label">{modelLabel}</span>
                  <ChevronDown className="h-3 w-3 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="end" className="w-56 max-h-[50vh] overflow-y-auto">
                {MODEL_CATALOG.map((m) => (
                  <DropdownMenuItem
                    key={m.id}
                    onClick={() => onModelChange(m.id)}
                    className="gap-2"
                  >
                    {m.id === projectModel && <Check className="h-4 w-4 shrink-0" />}
                    <span className={m.id === projectModel ? "" : "pl-4"}>{m.label}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="default"
              size="sm"
              className="send-btn"
              disabled={!text.trim() || sending}
              onClick={submit}
              title="Send"
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
