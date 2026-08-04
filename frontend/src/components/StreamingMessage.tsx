import { MarkdownContent } from "./ChatMessage";
import type { CanvasArtifact } from "./CanvasPane";
import { Icon } from "./Icon";
import { ThinkingBlock } from "./ThinkingBlock";
import { ThinkingPhrases } from "./ThinkingPhrases";

export interface ToolCallUI {
  id: string;
  name: string;
  arguments: string;
}

export interface StreamingDraft {
  thinking: string;
  content: string;
  tools: ToolCallUI[];
  provider: string;
  model: string;
}

interface StreamingMessageProps {
  draft: StreamingDraft;
  onOpenCanvas?: (artifact: CanvasArtifact) => void;
}

export function StreamingMessage({ draft, onOpenCanvas }: StreamingMessageProps) {
  return (
    <div className="assistant-msg">
      <div className="msg-avatar">AI</div>
      <div className="assistant-body">
        <div className="assistant-header">
          <span className="agent-name">openagent</span>
          <span className="msg-time">
            {draft.provider === "fallback" ? (
              <span className="fallback-badge">fallback · {draft.model}</span>
            ) : (
              <span className="msg-time live-dot">
                <span className="pulse-dot" /> <ThinkingPhrases compact />
              </span>
            )}
          </span>
        </div>

        {draft.thinking && <ThinkingBlock text={draft.thinking} />}

        {draft.tools.map((t) => (
          <div className="tool-card" key={t.id}>
            <div className="tool-card-header">
              <Icon name="terminal" size={14} />
              <span style={{ fontWeight: 500 }}>{t.name}</span>
              {t.arguments && (
                <span style={{ color: "var(--fg-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {t.arguments}
                </span>
              )}
            </div>
          </div>
        ))}

        {draft.content && <MarkdownContent text={draft.content} onOpenCanvas={onOpenCanvas} />}
      </div>
    </div>
  );
}