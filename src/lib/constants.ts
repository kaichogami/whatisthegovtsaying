export const COUNTRY_NAMES: Record<string, string> = {
  AE: "UAE",
  AR: "Argentina",
  AU: "Australia",
  BR: "Brazil",
  CA: "Canada",
  CH: "Switzerland",
  CN: "China",
  DE: "Germany",
  ES: "Spain",
  EU: "European Union",
  FR: "France",
  GB: "United Kingdom",
  ID: "Indonesia",
  IE: "Ireland",
  IN: "India",
  IT: "Italy",
  JP: "Japan",
  KR: "South Korea",
  NG: "Nigeria",
  NL: "Netherlands",
  NZ: "New Zealand",
  QA: "Qatar",
  RU: "Russia",
  SG: "Singapore",
  TH: "Thailand",
  TW: "Taiwan",
  UN: "United Nations",
  US: "United States",
  VN: "Vietnam",
  WHO: "WHO",
  ZA: "South Africa",
};

export const COUNTRY_FLAGS: Record<string, string> = {
  AE: "\u{1F1E6}\u{1F1EA}",
  AR: "\u{1F1E6}\u{1F1F7}",
  AU: "\u{1F1E6}\u{1F1FA}",
  BR: "\u{1F1E7}\u{1F1F7}",
  CA: "\u{1F1E8}\u{1F1E6}",
  CH: "\u{1F1E8}\u{1F1ED}",
  CN: "\u{1F1E8}\u{1F1F3}",
  DE: "\u{1F1E9}\u{1F1EA}",
  ES: "\u{1F1EA}\u{1F1F8}",
  EU: "\u{1F1EA}\u{1F1FA}",
  FR: "\u{1F1EB}\u{1F1F7}",
  GB: "\u{1F1EC}\u{1F1E7}",
  ID: "\u{1F1EE}\u{1F1E9}",
  IE: "\u{1F1EE}\u{1F1EA}",
  IN: "\u{1F1EE}\u{1F1F3}",
  IT: "\u{1F1EE}\u{1F1F9}",
  JP: "\u{1F1EF}\u{1F1F5}",
  KR: "\u{1F1F0}\u{1F1F7}",
  NG: "\u{1F1F3}\u{1F1EC}",
  NL: "\u{1F1F3}\u{1F1F1}",
  NZ: "\u{1F1F3}\u{1F1FF}",
  QA: "\u{1F1F6}\u{1F1E6}",
  RU: "\u{1F1F7}\u{1F1FA}",
  SG: "\u{1F1F8}\u{1F1EC}",
  TH: "\u{1F1F9}\u{1F1ED}",
  TW: "\u{1F1F9}\u{1F1FC}",
  UN: "\u{1F1FA}\u{1F1F3}",
  US: "\u{1F1FA}\u{1F1F8}",
  VN: "\u{1F1FB}\u{1F1F3}",
  WHO: "\u{1F3E5}",
  ZA: "\u{1F1FF}\u{1F1E6}",
};

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00Z");
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00Z");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Get previous day as YYYY-MM-DD */
export function prevDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

/** Get next day as YYYY-MM-DD */
export function nextDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
