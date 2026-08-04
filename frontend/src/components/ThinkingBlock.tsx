import { useState } from "react";
import { Icon } from "./Icon";

interface ThinkingBlockProps {
  text: string;
}

export function ThinkingBlock({ text }: ThinkingBlockProps) {
  const [showThinking, setShowThinking] = useState(true);

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
        {showThinking ? <Icon name="chevron-down" size={12} /> : <Icon name="chevron-right" size={12} />}
        <span>Thinking</span>
      </div>
      {showThinking && <pre className="thinking-body">{text}</pre>}
    </div>
  );
}