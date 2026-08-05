import { useState } from "react";

interface ThinkingBlockProps {
  text: string;
  defaultOpen?: boolean;
}

export function ThinkingBlock({ text, defaultOpen }: ThinkingBlockProps) {
  const [showThinking, setShowThinking] = useState(defaultOpen ?? false);

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
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Thinking</span>
      </div>
      {showThinking && <pre className="thinking-body">{text}</pre>}
    </div>
  );
}