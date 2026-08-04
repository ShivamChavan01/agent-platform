import type { CanvasArtifact } from "../components/CanvasPane";

const EXT_BY_LANG: Record<string, string> = {
  html: "html",
  htm: "html",
  svg: "svg",
  css: "css",
  js: "js",
  jsx: "jsx",
  ts: "ts",
  tsx: "tsx",
  python: "py",
  py: "py",
  go: "go",
  rust: "rs",
  rs: "rs",
  java: "java",
  c: "c",
  cpp: "cpp",
  json: "json",
  yaml: "yaml",
  yml: "yml",
  sql: "sql",
  sh: "sh",
  bash: "sh",
  md: "md",
  markdown: "md",
};

const DEFAULT_NAME_BY_LANG: Record<string, string> = {
  html: "index.html",
  svg: "preview.svg",
  css: "styles.css",
  js: "script.js",
  jsx: "App.jsx",
  ts: "script.ts",
  tsx: "App.tsx",
  python: "main.py",
  py: "main.py",
  go: "main.go",
  rust: "main.rs",
  rs: "main.rs",
  java: "Main.java",
  c: "main.c",
  cpp: "main.cpp",
  json: "data.json",
  sql: "query.sql",
  sh: "run.sh",
  bash: "run.sh",
  md: "README.md",
  markdown: "README.md",
};

/** Extract the first line of a code block for an explicit `path:` / filename hint. */
function hintFileName(code: string): string | null {
  const first = code.split("\n")[0] ?? "";
  const trimmed = first.trim();
  const m =
    /(?:path|file|filename)\s*[:=]\s*([\w./-]+\.[\w]+)/i.exec(trimmed) ??
    /^(?:#+\s*)?([\w./-]+\.[\w]+)\s*$/i.exec(trimmed);
  if (m) return m[1];
  return null;
}

export function deriveFileName(lang: string, code: string): string {
  const hinted = hintFileName(code);
  if (hinted) return hinted;
  const ext = EXT_BY_LANG[lang];
  if (ext) return `file.${ext}`;
  return DEFAULT_NAME_BY_LANG[lang] ?? "artifact.txt";
}

export interface FencedBlock {
  lang: string;
  code: string;
  name: string;
}

const FENCE_RE = /```(\w+)\s*\n([\s\S]*?)```/g;

/** Extract every fenced code block from assistant text as an artifact. */
export function extractArtifacts(text: string): FencedBlock[] {
  const blocks: FencedBlock[] = [];
  let m: RegExpExecArray | null;
  FENCE_RE.lastIndex = 0;
  while ((m = FENCE_RE.exec(text)) !== null) {
    const lang = m[1].toLowerCase();
    const code = m[2].replace(/\n$/, "");
    blocks.push({ lang, code, name: deriveFileName(lang, code) });
  }
  return blocks;
}

/**
 * A block counts as a canvas-worthy artifact when it is previewable
 * (html/svg) or long enough to be a real file rather than a snippet.
 */
export function isSubstantialArtifact(b: FencedBlock): boolean {
  const previewable = b.lang === "html" || b.lang === "svg";
  const hasName = /\.\w{1,5}$/.test(b.name) && b.name !== `file.${EXT_BY_LANG[b.lang] ?? "txt"}`;
  return previewable || hasName || b.code.trim().split("\n").length > 6;
}

/** Languages that can be rendered live in a sandboxed iframe preview. */
export function isPreviewable(lang: string): boolean {
  return lang === "html" || lang === "svg" || lang === "xml";
}

export function toCanvasArtifact(b: FencedBlock): CanvasArtifact {
  return { code: b.code, lang: b.lang, path: b.name };
}
