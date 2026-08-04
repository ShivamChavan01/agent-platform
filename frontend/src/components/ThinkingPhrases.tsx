import { useEffect, useState } from "react";

const PHRASES = [
  "Reasoning through it",
  "Weighing the options",
  "Working it out",
  "Piecing it together",
  "Running the numbers",
];

const ROTATE_MS = 1750;

interface ThinkingPhrasesProps {
  compact?: boolean;
}

export function ThinkingPhrases({ compact }: ThinkingPhrasesProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % PHRASES.length), ROTATE_MS);
    return () => clearInterval(id);
  }, []);

  return <span className={`thinking-phrase${compact ? " compact" : ""}`}>{PHRASES[index]}</span>;
}
