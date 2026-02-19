import Database from "better-sqlite3";
import path from "node:path";

const DB_PATH =
  process.env.DIGEST_DB_PATH ||
  path.join(process.cwd(), "data", "digests.db");

export interface ReleaseSummary {
  id: number;
  release_id: number;
  title: string;
  summary: string;
  original_url: string;
  ministry: string | null;
}

export interface CountryDigest {
  id: number;
  country_code: string;
  country_name: string;
  title: string;
  summary: string;
  releases: ReleaseSummary[];
}

export interface DailyDigest {
  id: number;
  date: string;
  global_title: string;
  global_summary: string;
  created_at: string;
}

export interface DigestPage {
  digest: DailyDigest;
  countries: CountryDigest[];
}

// Weekly types
export interface WeeklyCountryDigest {
  id: number;
  country_code: string;
  country_name: string;
  title: string;
  summary: string;
}

export interface WeeklyDigest {
  id: number;
  week_start: string;
  week_end: string;
  global_title: string;
  global_summary: string;
  created_at: string;
}

export interface WeeklyPage {
  digest: WeeklyDigest;
  countries: WeeklyCountryDigest[];
}

function getDb(): Database.Database {
  return new Database(DB_PATH, { readonly: true });
}

export function getLatestDigest(): DigestPage | null {
  const db = getDb();
  try {
    const row = db
      .prepare("SELECT * FROM daily_digest ORDER BY date DESC LIMIT 1")
      .get() as DailyDigest | undefined;
    if (!row) return null;
    return buildDigestPage(db, row);
  } finally {
    db.close();
  }
}

export function getDigestByDate(date: string): DigestPage | null {
  const db = getDb();
  try {
    const row = db
      .prepare("SELECT * FROM daily_digest WHERE date = ?")
      .get(date) as DailyDigest | undefined;
    if (!row) return null;
    return buildDigestPage(db, row);
  } finally {
    db.close();
  }
}

export function getAllDigestDates(): string[] {
  const db = getDb();
  try {
    const rows = db
      .prepare("SELECT date FROM daily_digest ORDER BY date DESC")
      .all() as { date: string }[];
    return rows.map((r) => r.date);
  } finally {
    db.close();
  }
}

// Weekly readers
export function getWeeklyDigest(weekEnd: string): WeeklyPage | null {
  const db = getDb();
  try {
    const row = db
      .prepare("SELECT * FROM weekly_digest WHERE week_end = ?")
      .get(weekEnd) as WeeklyDigest | undefined;
    if (!row) return null;
    return buildWeeklyPage(db, row);
  } finally {
    db.close();
  }
}

export function getAllWeeklyDates(): string[] {
  const db = getDb();
  try {
    const rows = db
      .prepare("SELECT week_end FROM weekly_digest ORDER BY week_end DESC")
      .all() as { week_end: string }[];
    return rows.map((r) => r.week_end);
  } finally {
    db.close();
  }
}

function buildDigestPage(db: Database.Database, digest: DailyDigest): DigestPage {
  const countryRows = db
    .prepare(
      "SELECT * FROM country_digest WHERE daily_digest_id = ? ORDER BY country_name"
    )
    .all(digest.id) as (CountryDigest & { daily_digest_id: number })[];

  const countries: CountryDigest[] = countryRows.map((c) => {
    const releases = db
      .prepare(
        "SELECT * FROM release_summary WHERE country_digest_id = ? ORDER BY id"
      )
      .all(c.id) as ReleaseSummary[];

    return {
      id: c.id,
      country_code: c.country_code,
      country_name: c.country_name,
      title: c.title || "",
      summary: c.summary,
      releases,
    };
  });

  return { digest, countries };
}

function buildWeeklyPage(db: Database.Database, digest: WeeklyDigest): WeeklyPage {
  const countryRows = db
    .prepare(
      "SELECT * FROM weekly_country_digest WHERE weekly_digest_id = ? ORDER BY country_name"
    )
    .all(digest.id) as (WeeklyCountryDigest & { weekly_digest_id: number })[];

  const countries: WeeklyCountryDigest[] = countryRows.map((c) => ({
    id: c.id,
    country_code: c.country_code,
    country_name: c.country_name,
    title: c.title || "",
    summary: c.summary,
  }));

  return { digest, countries };
}
