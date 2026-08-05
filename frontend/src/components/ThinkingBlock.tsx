import { useState } from "react";
import { Logo } from "./Logo";

interface ThinkingBlockProps {
  text: string;
}

export function ThinkingBlock({ text }: ThinkingBlockProps) {
  const [showThinking, setShowThinking] = useState(false);

  return (
    <div className="thinking-block">
      <div
        className="thinking-toggle"
        role="button"
        tabIndex={0}
        onClick={() => setShowThinking((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setShowThinking((v) => !v);
          }
        }}
      >
        <span className="spin-logo">
          <Logo size={14} />
        </span>
        <span>Thinking</span>
      </div>
      {showThinking && <pre className="thinking-body">{text}</pre>}
    </div>
  );
}