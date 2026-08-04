import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Paperclip, Send, X } from "lucide-react";

interface ComposerProps {
  sending: boolean;
  attachment: { name: string } | null;
  onRemoveAttachment: () => void;
  onSend: (text: string) => void;
  onAttach: (file: File) => void;
}

export function Composer({ sending, attachment, onRemoveAttachment, onSend, onAttach }: ComposerProps) {
  const [text, setText] = useState("");
  const sendOnEnter = () => localStorage.getItem("aw_send_on_enter") !== "false";
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const value = text.trim();
    if (!value || sending) return;
    setText("");
    onSend(value);
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
        {attachment && (
          <Badge variant="secondary" className="composer-attachment gap-1.5 pr-1.5">
            <Paperclip className="h-3 w-3 shrink-0" />
            <span className="composer-attachment-name">{attachment.name}</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-4 w-4 p-0 hover:bg-transparent hover:text-accent-rose shrink-0"
              title="Remove attachment"
              aria-label="Remove attachment"
              onClick={onRemoveAttachment}
            >
              <X className="h-3 w-3" />
            </Button>
          </Badge>
        )}
        <div className="input-box">
          <Textarea
            className="composer-textarea border-0 bg-transparent focus-visible:ring-0 shadow-none resize-none"
            rows={1}
            placeholder="Message AI Workspace..."
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
              title="Attach a file"
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </Button>
            <input
              ref={fileRef}
              type="file"
              hidden
              accept=".txt,.md,.markdown,.rst,.csv,.json,.log,.pdf,.docx,.py,.js,.ts,.tsx,.jsx,.html,.css,.xml,.yaml,.yml,.toml,.ini,.cfg,.sql,.sh,.go,.rs,.rb,.c,.h,.cpp,.hpp,.java,.kt,.swift"
              title=".txt/.md/.csv/.json/code files, .pdf, .docx (max 10MB)"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onAttach(f);
                e.target.value = "";
              }}
            />
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
