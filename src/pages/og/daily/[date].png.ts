import type { APIRoute, GetStaticPaths } from "astro";
import { getAllDigestDates, getDigestByDate } from "../../../lib/digest";
import { formatDate } from "../../../lib/constants";
import { stripMd } from "../../../lib/md";
import { generateOgImage } from "../../../lib/og";

export const getStaticPaths: GetStaticPaths = () => {
  return getAllDigestDates().map((date) => ({ params: { date } }));
};

export const GET: APIRoute = async ({ params }) => {
  const page = getDigestByDate(params.date!);
  if (!page) return new Response("Not found", { status: 404 });

  const headline = stripMd(page.digest.global_title || "Government Press Digest");
  const description = page.digest.global_summary.replace(/[*_#>\[\]]/g, "").slice(0, 160);
  const dateLabel = formatDate(page.digest.date);

  const png = await generateOgImage(headline, description, dateLabel);

  return new Response(png, {
    headers: { "Content-Type": "image/png" },
  });
};
