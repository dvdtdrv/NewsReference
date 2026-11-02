// Step 4: build the search index for the website's search page (site/tarsene.html).
//
// Uses Pagefind (https://pagefind.app), a free search tool for static sites. It splits the index into
// small pieces in site/pagefind/, and the browser downloads only the pieces that match what you typed,
// so search stays fast even with years of articles.
//
// Everything in the archive goes in:
//   - every story  (data/stories/YYYY-MM-DD.json)  -> found by its title and its articles' headlines
//   - every article (data/articles/YYYY-MM.json)   -> found by its headline and the start of its summary
//
// Run after build_site.py:   node build_search.mjs
// (needs Node.js and, once, "npm install" in this folder)

import fs from "node:fs";
import path from "node:path";
import * as pagefind from "pagefind";

const DATA = "data";
const OUT = path.join("site", "pagefind");
const SUMMARY_CHARS = 200;

const readJson = f => JSON.parse(fs.readFileSync(f, "utf8"));
const jsonFiles = dir => fs.existsSync(dir) ? fs.readdirSync(dir).filter(n => n.endsWith(".json")).sort() : [];

// each article's own photo, if collect.py found it on the article page
const photos = fs.existsSync(path.join(DATA, "page_images.json")) ? readJson(path.join(DATA, "page_images.json")) : {};
const photoOf = a => photos[a.link] || a.image || "";

// 1. stories, and which story each article belongs to
const storyOf = new Map();   // article link -> { href, title }
const stories = [];
for (const name of jsonFiles(path.join(DATA, "stories"))) {
  const day = name.slice(0, -5);
  for (const s of readJson(path.join(DATA, "stories", name)).stories) {
    const href = `archive/${day}.html#s-${s.id}`;
    stories.push({ s, href });
    for (const a of s.articles) storyOf.set(a.link, { href, title: s.headline });
  }
}

// 2. articles (each link once)
const articles = new Map();
for (const name of jsonFiles(path.join(DATA, "articles"))) {
  const month = readJson(path.join(DATA, "articles", name));
  for (const a of (Array.isArray(month) ? month : month.articles)) {
    if (a.link && a.title && !articles.has(a.link)) articles.set(a.link, a);
  }
}

// 3. the index
const { index, errors } = await pagefind.createIndex({ forceLanguage: "bg" });
if (errors.length) throw new Error(errors.join("\n"));

for (const { s, href } of stories) {
  await index.addCustomRecord({
    url: href,
    language: "bg",
    content: [s.headline, ...s.articles.map(a => a.title)].join(". "),
    meta: {
      title: s.headline,
      href,
      outlets: s.outlets.join(", "),
      count: String(s.outlet_count),
      first: s.first_seen,
      last: s.last_updated,
      image: s.articles.map(photoOf).find(Boolean) || ""
    },
    filters: { type: ["story"] },
    sort: { date: s.last_updated }
  });
}

for (const a of articles.values()) {
  const story = storyOf.get(a.link);
  const summary = (a.summary || "").slice(0, SUMMARY_CHARS);
  await index.addCustomRecord({
    url: a.link,
    language: "bg",
    content: summary ? `${a.title}. ${summary}` : a.title,
    meta: {
      title: a.title,
      href: a.link,
      outlet: a.outlet,
      published: a.published || "",
      image: photoOf(a),
      story: story ? story.title : "",
      story_href: story ? story.href : ""
    },
    filters: { type: ["article"], outlet: [a.outlet] },
    sort: { date: a.published || "" }
  });
}

fs.rmSync(OUT, { recursive: true, force: true });
const written = await index.writeFiles({ outputPath: OUT });
if (written.errors.length) throw new Error(written.errors.join("\n"));
await pagefind.close();
console.log(`Search index: ${stories.length} stories, ${articles.size} articles -> ${OUT}`);
