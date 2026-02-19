import type { APIRoute, GetStaticPaths } from "astro";
import { getAllWeeklyDates, getWeeklyDigest } from "../../../lib/digest";
import { formatDateShort, formatDate } from "../../../lib/constants";
import { stripMd } from "../../../lib/md";
import { generateOgImage } from "../../../lib/og";

export const getStaticPaths: GetStaticPaths = () => {
  return getAllWeeklyDates().map((date) => ({ params: { date } }));
};

export const GET: APIRoute = async ({ params }) => {
  const page = getWeeklyDigest(params.date!);
  if (!page) return new Response("Not found", { status: 404 });

  const headline = stripMd(page.digest.global_title || "Weekly Government Digest");
  const description = page.digest.global_summary.replace(/[*_#>\[\]|]/g, "").slice(0, 160);
  const dateLabel = `Week of ${formatDateShort(page.digest.week_start)} — ${formatDate(page.digest.week_end)}`;

  const png = await generateOgImage(headline, description, dateLabel);

  return new Response(png, {
    headers: { "Content-Type": "image/png" },
  });
};
