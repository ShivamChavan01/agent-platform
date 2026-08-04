import { useState } from "react";
import { Icon } from "./Icon";

export interface CanvasArtifact {
  code: string;
  lang: string;
  path?: string;
}

interface CanvasPaneProps {
  artifact: CanvasArtifact;
  onClose: () => void;
}

const PREVIEWABLE = new Set(["html", "svg", "xml"]);

export function CanvasPane({ artifact, onClose }: CanvasPaneProps) {
  const [tab, setTab] = useState<"code" | "preview">("code");
  const [copied, setCopied] = useState(false);
  const previewable = PREVIEWABLE.has(artifact.lang.toLowerCase());

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(artifact.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <aside className="canvas-pane">
      <div className="canvas-tabs">
        <button
          className={`canvas-tab ${tab === "code" ? "active" : ""}`}
          onClick={() => setTab("code")}
        >
          Code
        </button>
        <button
          className={`canvas-tab ${tab === "preview" ? "active" : ""}`}
          onClick={() => previewable && setTab("preview")}
          disabled={!previewable}
          title={previewable ? "Render preview" : "Preview is available for HTML/SVG"}
          style={previewable ? undefined : { opacity: 0.4, cursor: "default" }}
        >
          Preview
        </button>
        <span className="code-lang" style={{ marginLeft: 8 }}>
          {artifact.lang}
        </span>
        <div style={{ flex: 1 }} />
        <button className="code-header-btn" onClick={copy}>
          <Icon name="copy" size={12} />
          {copied ? "Copied" : "Copy"}
        </button>
        <button className="icon-btn" onClick={onClose} title="Close canvas">
          <Icon name="eyeOff" size={14} />
        </button>
      </div>
      <div className="canvas-body">
        {tab === "preview" && previewable ? (
          <iframe
            title="Artifact preview"
            sandbox="allow-scripts"
            srcDoc={artifact.code}
            style={{ width: "100%", height: "100%", border: "none", background: "#fff" }}
          />
        ) : (
          <pre style={{ padding: "14px 16px", fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: 1.6, color: "var(--fg-muted)", whiteSpace: "pre-wrap", wordBreak: "break-word", background: "var(--surface-code)", minHeight: "100%" }}>
            {artifact.code}
          </pre>
        )}
      </div>
    </aside>
  );
}
