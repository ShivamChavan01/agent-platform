import { useState } from "react";
import type { Message } from "../lib/types";
import { timeAgo } from "../lib/time";
import { Icon } from "./Icon";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  if (message.role === "user") {
    return <div className="user-bubble">{message.content}</div>;
  }

  if (message.role === "tool") {
    return (
      <div className="tool-card">
        <div className="tool-card-header">
          <Icon name="terminal" size={14} />
          <span style={{ fontWeight: 500 }}>{message.tool_name || "Tool"}</span>
          {message.tool_arguments ? (
            <span style={{ color: "var(--fg-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {message.tool_arguments}
            </span>
          ) : null}
        </div>
        <div className="tool-card-body">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="assistant-msg">
      <div className="msg-avatar">AI</div>
      <div className="assistant-body">
        <div className="assistant-header">
          <span className="agent-name">AI Workspace</span>
          <span className="msg-time">{timeAgo(message.created_at)}</span>
        </div>
        <MarkdownContent text={message.content} />
      </div>
    </div>
  );
}

function MarkdownContent({ text }: { text: string }) {
  const segments = splitCodeBlocks(text);
  return (
    <div className="assistant-content">
      {segments.map((seg, i) =>
        seg.kind === "code" ? (
          <CodeBlock key={i} lang={seg.lang ?? "text"} code={seg.code ?? ""} />
        ) : (
          <p key={i}>{seg.text ?? ""}</p>
        )
      )}
    </div>
  );
}

interface Segment {
  kind: "text" | "code";
  text?: string;
  code?: string;
  lang?: string;
}

function splitCodeBlocks(text: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```(\w*)\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      segments.push({ kind: "text", text: text.slice(last, m.index) });
    }
    segments.push({ kind: "code", lang: m[1] || "text", code: m[2] });
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    segments.push({ kind: "text", text: text.slice(last) });
  }
  return segments;
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-lang">{lang}</span>
        <button className="code-header-btn" onClick={copy}>
          <Icon name="copy" size={12} />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="code-body">{code}</pre>
    </div>
  );
}
