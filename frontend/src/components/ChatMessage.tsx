import { isValidElement, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../lib/types";
import type { CanvasArtifact } from "./CanvasPane";
import { timeAgo } from "../lib/time";
import { Icon } from "./Icon";
import { ThinkingBlock } from "./ThinkingBlock";
import { deriveFileName, isPreviewable, isSubstantialArtifact, toCanvasArtifact, type FencedBlock } from "../lib/artifacts";

interface ChatMessageProps {
  message: Message;
  onOpenCanvas?: (artifact: CanvasArtifact) => void;
}

export function ChatMessage({ message, onOpenCanvas }: ChatMessageProps) {
  if (message.role === "user") {
    return <div className="user-bubble">{message.content}</div>;
  }

  if (message.role === "tool") {
    const content = message.content || "";
    const lines = content.split("\n");
    const preview = lines.slice(0, 3).join("\n");
    const isLong = lines.length > 4 || content.length > 400;

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
        <ToolCardBody content={content} preview={preview} isLong={isLong} />
      </div>
    );
  }

  return (
    <div className="assistant-msg">
      <div className="msg-avatar">AI</div>
      <div className="assistant-body">
        <div className="assistant-header">
          <span className="agent-name">openagent</span>
          <span className="msg-time">{timeAgo(message.created_at)}</span>
        </div>
        {message.reasoning && <ThinkingBlock text={message.reasoning} />}
        <MarkdownContent text={message.content} onOpenCanvas={onOpenCanvas} />
      </div>
    </div>
  );
}

function ToolCardBody({ content, preview, isLong }: { content: string; preview: string; isLong: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (!isLong) {
    return <div className="tool-card-body">{content}</div>;
  }

  return (
    <div className="tool-card-body-wrap">
      <div className={`tool-card-body ${expanded ? "expanded" : "collapsed"}`}>
        {expanded ? content : preview}
      </div>
      <button className="tool-card-toggle" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Show less ▴" : `Show full result (${content.length} chars) ▾`}
      </button>
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
              const block: FencedBlock = { lang: lang ?? "text", code, name: deriveFileName(lang ?? "text", code) };
              if (onOpenCanvas && isSubstantialArtifact(block)) {
                if (isPreviewable(block.lang)) {
                  return <InlinePreview block={block} onExpand={() => onOpenCanvas(toCanvasArtifact(block))} />;
                }
                return <ArtifactCard block={block} onOpen={() => onOpenCanvas(toCanvasArtifact(block))} />;
              }
              return <CodeBlock lang={lang ?? "text"} code={code} onOpenCanvas={onOpenCanvas} />;
            }
            return (
              <code className="md-inline-code" {...props}>
                {children}
              </code>
            );
          },
          pre({ children }) {
            // react-markdown hands pre the un-evaluated code component element;
            // our code override already emits a self-contained block element
            // (ArtifactCard / CodeBlock), so drop the default <pre> wrapper.
            return isValidElement(children) ? <>{children}</> : <pre>{children}</pre>;
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function artifactIcon(lang: string): string {
  if (lang === "html" || lang === "svg" || lang === "xml") return "eye";
  if (lang === "sh" || lang === "bash") return "terminal";
  return "code";
}

export function ArtifactCard({ block, onOpen }: { block: FencedBlock; onOpen: () => void }) {
  return (
    <button type="button" className="artifact-card" onClick={onOpen} title={`Open ${block.name} in Canvas`}>
      <span className="artifact-card-icon">
        <Icon name={artifactIcon(block.lang)} size={16} />
      </span>
      <span className="artifact-card-meta">
        <span className="artifact-card-name">{block.name}</span>
        <span className="artifact-card-hint">Click to view in Canvas</span>
      </span>
      <span className="code-lang">{block.lang}</span>
    </button>
  );
}

const PREVIEW_PROBE = `
<script>
(() => {
  "use strict";
  var send = function () {
    try {
      parent.postMessage({ __oap: 1, h: Math.ceil(document.documentElement.scrollHeight) }, "*");
    } catch (e) {}
  };
  send();
  window.addEventListener("resize", send);
  if (window.ResizeObserver) new ResizeObserver(send).observe(document.documentElement);
})();
</script>`;

function withProbe(code: string): string {
  if (/<\/body\s*>/i.test(code)) return code.replace(/<\/body\s*>/i, PREVIEW_PROBE + "</body>");
  return code + PREVIEW_PROBE;
}

export function InlinePreview({ block, onExpand }: { block: FencedBlock; onExpand: () => void }) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState<number | null>(null);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const onMessage = (event: MessageEvent) => {
      if (event.source !== frame.contentWindow) return;
      const data = event.data as { __oap?: number; h?: unknown } | null;
      if (!data || data.__oap !== 1) return;
      const h = Number(data.h);
      if (Number.isFinite(h) && h > 0) setHeight(Math.min(h, Math.max(360, window.innerHeight * 0.8)));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <div className="inline-preview">
      <div className="inline-preview-header">
        <Icon name={artifactIcon(block.lang)} size={13} />
        <span className="inline-preview-name">{block.name}</span>
        <span className="code-lang">{block.lang}</span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          className="code-header-btn"
          onClick={onExpand}
          title="Open in Canvas for full-size viewing and code inspection"
        >
          <Icon name="sidebar" size={12} />
          Expand
        </button>
      </div>
      <iframe
        ref={frameRef}
        title={`Live preview: ${block.name}`}
        sandbox="allow-scripts"
        srcDoc={withProbe(block.code)}
        loading="lazy"
        style={height ? { height } : undefined}
      />
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
