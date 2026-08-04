import { useRef, useState } from "react";
import { Icon } from "./Icon";

interface ComposerProps {
  sending: boolean;
  onSend: (text: string) => void;
  onAttach: (file: File) => void;
}

export function Composer({ sending, onSend, onAttach }: ComposerProps) {
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
        <div className="input-box">
          <textarea
            className="composer-textarea"
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
            <button
              className="composer-btn"
              title="Attach a file"
              onClick={() => fileRef.current?.click()}
            >
              <Icon name="paperclip" size={14} />
              Attach
            </button>
            <input
              ref={fileRef}
              type="file"
              hidden
              accept=".txt,.pdf"
              title="Only .txt and .pdf are supported (max 10MB)"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onAttach(f);
                e.target.value = "";
              }}
            />
            <button
              className="send-btn"
              disabled={!text.trim() || sending}
              onClick={submit}
              title="Send"
            >
              <Icon name="send" size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
