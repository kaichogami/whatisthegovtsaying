import satori from "satori";
import sharp from "sharp";

const FONT_CACHE: { regular?: ArrayBuffer; bold?: ArrayBuffer } = {};

async function loadFonts() {
  if (!FONT_CACHE.regular) {
    const [regular, bold] = await Promise.all([
      fetch(
        "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.woff"
      ).then((r) => r.arrayBuffer()),
      fetch(
        "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-700-normal.woff"
      ).then((r) => r.arrayBuffer()),
    ]);
    FONT_CACHE.regular = regular;
    FONT_CACHE.bold = bold;
  }
  return FONT_CACHE as { regular: ArrayBuffer; bold: ArrayBuffer };
}

export async function generateOgImage(
  headline: string,
  description: string,
  dateLabel: string
): Promise<Buffer> {
  const fonts = await loadFonts();

  const truncatedDesc =
    description.length > 140 ? description.slice(0, 137) + "..." : description;

  const svg = await satori(
    {
      type: "div",
      props: {
        style: {
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#1a1a1a",
          padding: "60px 64px",
          fontFamily: "Inter",
        },
        children: [
          {
            type: "div",
            props: {
              style: { display: "flex", flexDirection: "column" },
              children: [
                {
                  type: "div",
                  props: {
                    style: {
                      fontSize: 22,
                      fontWeight: 400,
                      color: "#888888",
                      letterSpacing: "0.15em",
                      textTransform: "uppercase",
                      marginBottom: 16,
                    },
                    children: "What Is The Govt Saying",
                  },
                },
                {
                  type: "div",
                  props: {
                    style: {
                      display: "flex",
                      width: "100%",
                      height: 3,
                      backgroundColor: "#e2e0dc",
                      marginBottom: 32,
                    },
                  },
                },
                {
                  type: "div",
                  props: {
                    style: {
                      fontSize: 48,
                      fontWeight: 700,
                      color: "#ffffff",
                      lineHeight: 1.2,
                      marginBottom: 24,
                    },
                    children:
                      headline.length > 90
                        ? headline.slice(0, 87) + "..."
                        : headline,
                  },
                },
                {
                  type: "div",
                  props: {
                    style: {
                      fontSize: 22,
                      fontWeight: 400,
                      color: "#aaaaaa",
                      lineHeight: 1.5,
                    },
                    children: truncatedDesc,
                  },
                },
              ],
            },
          },
          {
            type: "div",
            props: {
              style: {
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderTop: "1px solid #333333",
                paddingTop: 20,
              },
              children: [
                {
                  type: "div",
                  props: {
                    style: {
                      fontSize: 20,
                      color: "#888888",
                    },
                    children: dateLabel,
                  },
                },
                {
                  type: "div",
                  props: {
                    style: {
                      fontSize: 16,
                      color: "#555555",
                    },
                    children: "whatisthegovtsaying.com",
                  },
                },
              ],
            },
          },
        ],
      },
    },
    {
      width: 1200,
      height: 630,
      fonts: [
        { name: "Inter", data: fonts.regular, weight: 400, style: "normal" },
        { name: "Inter", data: fonts.bold, weight: 700, style: "normal" },
      ],
    }
  );

  return sharp(Buffer.from(svg)).png().toBuffer();
}
