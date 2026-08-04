import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../lib/types";
import type { CanvasArtifact } from "./CanvasPane";
import { timeAgo } from "../lib/time";
import { Icon } from "./Icon";
import { ThinkingBlock } from "./ThinkingBlock";

interface ChatMessageProps {
  message: Message;
  onOpenCanvas?: (artifact: CanvasArtifact) => void;
}

export function ChatMessage({ message, onOpenCanvas }: ChatMessageProps) {
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
        {message.reasoning && <ThinkingBlock text={message.reasoning} />}
        <MarkdownContent text={message.content} onOpenCanvas={onOpenCanvas} />
      </div>
    </div>
  );
}

export function MarkdownContent({ text, onOpenCanvas }: { text: string; onOpenCanvas?: (a: CanvasArtifact) => void }) {
  return (
    <div className="assistant-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          code({ className, children, ...props }) {
            const lang = /language-(\w+)/.exec(className ?? "")?.[1];
            const code = String(children ?? "").replace(/\n$/, "");
            const isBlock = className ? (className as string).includes("language-") : code.includes("\n");
            if (isBlock) {
              return <CodeBlock lang={lang ?? "text"} code={code} onOpenCanvas={onOpenCanvas} />;
            }
            return (
              <code className="md-inline-code" {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function CodeBlock({ lang, code, onOpenCanvas }: { lang: string; code: string; onOpenCanvas?: (a: CanvasArtifact) => void }) {
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
        {onOpenCanvas && (
          <button className="code-header-btn" onClick={() => onOpenCanvas({ code, lang })}>
            <Icon name="sidebar" size={12} />
            Canvas
          </button>
        )}
      </div>
      <pre className="code-body">
        <code>{code}</code>
      </pre>
    </div>
  );
}
