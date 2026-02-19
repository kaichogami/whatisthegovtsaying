import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://whatisthegovtsaying.com",
  output: "static",
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    sitemap({
      filter: (page) => !page.includes("/og/"),
      changefreq: "daily",
      priority: 0.7,
      serialize(item) {
        if (item.url.endsWith("whatisthegovtsaying.com/")) {
          item.priority = 1.0;
          item.changefreq = "daily";
        } else if (item.url.includes("/weekly/")) {
          item.priority = 0.8;
          item.changefreq = "weekly";
        } else if (item.url.includes("/archive/")) {
          item.priority = 0.6;
          item.changefreq = "monthly";
        } else if (item.url.includes("/privacy")) {
          item.priority = 0.2;
          item.changefreq = "yearly";
        }
        return item;
      },
    }),
  ],
});
