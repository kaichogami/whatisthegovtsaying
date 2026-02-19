import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

export function md(text: string): string {
  return marked.parse(text, { async: false }) as string;
}

/** Strip markdown syntax for use in plain text contexts (titles, meta tags). */
export function stripMd(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#+\s*/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}
