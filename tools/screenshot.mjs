// Screenshot preview pages at TRMNL X geometry (1872x1404; the framework zooms
// the 1040x780 CSS screen by its 1.8 pixel ratio) and report overflowing text.
//   node tools/screenshot.mjs URL OUT.png [URL OUT.png ...]
// Needs Playwright with Chromium.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const pairs = [];
for (let i = 0; i < args.length; i += 2) pairs.push([args[i], args[i + 1]]);
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1872, height: 1404 }, deviceScaleFactor: 1 });
let bad = 0;
for (const [url, png] of pairs) {
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  const report = await page.evaluate(() => {
    const out = [];
    const layout = document.querySelector('.layout').getBoundingClientRect();
    for (const el of document.querySelectorAll('.layout *')) {
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const tag = el.className || el.tagName;
      if (r.right > layout.right + 1 || r.bottom > layout.bottom + 1 || r.left < layout.left - 1 || r.top < layout.top - 1)
        out.push(`outside layout: ${tag} ${JSON.stringify([r.left, r.top, r.right, r.bottom].map(Math.round))}`);
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
        out.push(`clipped x: ${tag}`);
      if (el.children.length === 0 && el.scrollWidth > el.clientWidth + 1)
        out.push(`text wider than box: ${tag} "${el.textContent.trim().slice(0, 40)}"`);
    }
    const img = document.querySelector('.layout img');
    return { layout: [layout.width, layout.height].map(Math.round),
             img: img ? [img.naturalWidth, img.naturalHeight, Math.round(img.getBoundingClientRect().width), Math.round(img.getBoundingClientRect().height)] : null,
             out };
  });
  await page.screenshot({ path: png });
  console.log(url, JSON.stringify(report));
  bad += report.out.length;
  await page.close();
}
await browser.close();
process.exit(bad ? 1 : 0);
