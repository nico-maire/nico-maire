// Records the two README GIFs from the live portfolio running locally:
//   assets/readme/nicos-desktop.gif  office -> power on -> boot -> desktop, projects, terminal, themes
//   assets/readme/nicos-phone.gif    Nokia-style phone UI
//
// Needs Chromium, ffmpeg and `npm i playwright-core`. Usage:
//   (cd ../nico-maire.github.io && python3 -m http.server 8000) &
//   CHROME=/path/to/chrome node tools/record_gifs.mjs [http://localhost:8000/]
//
// Frames are captured losslessly with the DevTools screencast, so the GIF has no video artefacts.
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BASE = process.argv[2] || 'http://localhost:8000/';
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const OUT = path.join(ROOT, 'assets', 'readme');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'nicos-gif-'));

async function launch({ width, height, mobile = false, storage = {} }) {
  const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile, locale: 'en-US' });
  await ctx.addInitScript((st) => {
    try { localStorage.clear(); for (const [k, v] of Object.entries(st)) localStorage.setItem(k, v); } catch { /* ignore */ }
  }, storage);
  return { browser, page: await ctx.newPage() };
}

// Saves every screencast frame with its timestamp and writes an ffmpeg concat list.
async function record(page, name, script) {
  const dir = path.join(TMP, name);
  fs.mkdirSync(dir);
  const frames = [];
  const cdp = await page.context().newCDPSession(page);
  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    const file = path.join(dir, `f${String(frames.length).padStart(5, '0')}.png`);
    fs.writeFileSync(file, Buffer.from(data, 'base64'));
    frames.push({ file, t: metadata.timestamp });
    try { await cdp.send('Page.screencastFrameAck', { sessionId }); } catch { /* closing */ }
  });
  await cdp.send('Page.startScreencast', { format: 'png', everyNthFrame: 1 });
  await script();
  await page.waitForTimeout(150);
  await cdp.send('Page.stopScreencast');
  const end = Date.now() / 1000;
  const lines = frames.flatMap((f, i) => [`file '${f.file}'`, `duration ${Math.max(0.001, (frames[i + 1]?.t ?? end) - f.t).toFixed(4)}`]);
  lines.push(`file '${frames.at(-1).file}'`);
  fs.writeFileSync(path.join(dir, 'list.txt'), lines.join('\n'));
  const mp4 = path.join(TMP, `${name}.mp4`);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '10', mp4]);
  return mp4;
}

function toGif(mp4, gif, { speed, width, colors, dither, fade = '' }) {
  const len = Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4])) / speed;
  const fades = `fade=t=in:st=0:d=0.35${fade},fade=t=out:st=${(len - 0.6).toFixed(2)}:d=0.6${fade}`;
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', mp4, '-filter_complex',
    `setpts=PTS/${speed},fps=12,scale=${width}:-1:flags=${width > 400 ? 'lanczos' : 'area'},${fades},split[a][b];` +
    `[a]palettegen=max_colors=${colors}:stats_mode=diff[p];[b][p]paletteuse=dither=${dither}:diff_mode=rectangle`, gif]);
  console.log(`${path.basename(gif)}: ${(fs.statSync(gif).size / 1e6).toFixed(1)} MB, ${len.toFixed(1)} s`);
}

// ------------------------------------------------------------------------------------------ helpers
const center = async (page, sel) => {
  const b = await page.locator(sel).first().boundingBox();
  if (!b) throw new Error(`not found: ${sel}`);
  return [b.x + b.width / 2, b.y + b.height / 2];
};

// Draws the page's own pixel cursor as an element: headless screenshots do not include the pointer.
async function fakeCursor(page, x, y) {
  await page.evaluate(() => {
    const el = Object.assign(document.createElement('img'), { id: 'rec-cursor' });
    Object.assign(el.style, { position: 'fixed', left: 0, top: 0, zIndex: 2147483647, pointerEvents: 'none', imageRendering: 'pixelated' });
    document.documentElement.append(el);
    const arrow = getComputedStyle(document.documentElement).getPropertyValue('--cur-arrow-classic').match(/url\("?(data:[^")]+)/)?.[1];
    window.recCursor = (cx, cy) => {
      const m = getComputedStyle(document.elementFromPoint(cx, cy) || document.body).cursor.match(/url\("?(data:[^")]+)"?\)\s*(\d+)?\s*(\d+)?/);
      const src = m ? m[1] : arrow;
      if (src && el.src !== src) el.src = src;
      el.style.transform = `translate(${cx - (m ? +(m[2] || 0) : 0)}px, ${cy - (m ? +(m[3] || 0) : 0)}px)`;
    };
    window.addEventListener('pointermove', (e) => window.recCursor(e.clientX, e.clientY), true);
  });
  await page.mouse.move(x, y);
  await page.evaluate(([a, b]) => window.recCursor(a, b), [x, y]);
  return [x, y];
}

function mouse(page, start) {
  let pos = start;
  const moveTo = async ([x, y], ms = 700) => {
    const n = Math.max(6, Math.round(ms / 40));
    for (let i = 1; i <= n; i++) {
      const k = i / n;
      const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
      await page.mouse.move(pos[0] + (x - pos[0]) * e, pos[1] + (y - pos[1]) * e);
      await page.waitForTimeout(ms / n);
    }
    pos = [x, y];
  };
  return {
    to: async (sel, ms) => moveTo(await center(page, sel), ms),
    click: async () => { await page.mouse.down(); await page.mouse.up(); },
    dbl: () => page.mouse.dblclick(...pos),
  };
}

// ---------------------------------------------------------------------------------------- desktop
async function desktop() {
  const { browser, page } = await launch({ width: 1280, height: 720, storage: { 'nicos:welcomed': 'true' } });
  // Chromium builds without H.264 cannot play the MP4 demo: serve a VP9 copy under the same URL.
  const webm = path.join(TMP, 'demo.webm');
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', new URL('assets/media/citasalon/demo.mp4', BASE).href, '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '34', '-an', '-deadline', 'realtime', '-cpu-used', '8', webm]);
  await page.route('**/citasalon/demo.mp4', (r) => r.fulfill({ status: 200, contentType: 'video/webm', body: fs.readFileSync(webm) }));
  await page.goto(`${BASE}?lang=en`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.power-btn');
  await page.waitForTimeout(600);
  // The rolling CRT band repaints every pixel on every frame, which bloats a GIF: freeze it.
  await page.addStyleTag({ content: '.crt-fx::after,.crt-flicker{animation:none!important}' });
  const m = mouse(page, await fakeCursor(page, 1000, 260));
  const mp4 = await record(page, 'desktop', async () => {
    await page.waitForTimeout(1300);
    await m.to('.power-btn', 900);
    await page.waitForTimeout(250);
    await m.click();
    await page.waitForTimeout(3600); // zoom and part of the BIOS boot
    await page.keyboard.press('Space');
    await page.waitForSelector('.d-icon[data-id="projects"]', { timeout: 15000 });
    await page.waitForTimeout(900);
    for (const sel of ['.d-icon[data-id="projects"]', '.fs-item[title="Entrepreneurship"]', '.fs-item >> text=CitaSalon']) {
      await m.to(sel, 700);
      await page.waitForTimeout(150);
      await m.dbl();
      await page.waitForTimeout(900);
    }
    await m.to('.vp-big', 500);
    await m.click();
    await page.waitForTimeout(2200);
    await m.to('.tb-start', 800);
    await m.click();
    await page.waitForTimeout(350);
    await m.to('.os-start .menu-item >> text=Terminal', 450);
    await m.click();
    await page.waitForSelector('.term-input');
    await page.waitForTimeout(600);
    for (const ch of 'neofetch') { await page.keyboard.type(ch); await page.waitForTimeout(90 + Math.random() * 40); }
    await page.keyboard.press('Enter');
    await page.waitForTimeout(2000);
    await m.to('.tb-theme', 800);
    for (let i = 0; i < 3; i++) { await page.waitForTimeout(i ? 1300 : 200); await m.click(); }
    await page.waitForTimeout(1000);
  });
  await browser.close();
  toGif(mp4, path.join(OUT, 'nicos-desktop.gif'), { speed: 1.45, width: 800, colors: 160, dither: 'bayer:bayer_scale=5' });
}

// ------------------------------------------------------------------------------------------ phone
async function phone() {
  const { browser, page } = await launch({ width: 360, height: 640, mobile: true });
  await page.goto(`${BASE}?lang=en`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  await page.addStyleTag({ content: `.rec-tap{position:fixed;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;
    background:rgba(20,40,20,.28);border:2px solid rgba(20,40,20,.55);pointer-events:none;z-index:2147483647;animation:rec-tap .5s ease-out forwards}
    @keyframes rec-tap{0%{transform:scale(.5);opacity:1}100%{transform:scale(1.25);opacity:0}}` });
  const tap = async (sel, wait = 650) => {
    const [x, y] = await center(page, sel);
    await page.evaluate(([a, b]) => {
      const d = Object.assign(document.createElement('div'), { className: 'rec-tap' });
      Object.assign(d.style, { left: `${a}px`, top: `${b}px` });
      document.documentElement.append(d);
      setTimeout(() => d.remove(), 600);
    }, [x, y]);
    await page.waitForTimeout(140);
    await page.touchscreen.tap(x, y);
    await page.waitForTimeout(wait);
  };
  const scroll = (dy, ms) => page.evaluate(([d, t]) => new Promise((done) => {
    const el = document.querySelector('.ph-body');
    const s0 = el.scrollTop;
    const t0 = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - t0) / t);
      el.scrollTop = s0 + d * (k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2);
      if (k < 1) requestAnimationFrame(step); else done();
    };
    requestAnimationFrame(step);
  }), [dy, ms]);
  const mp4 = await record(page, 'phone', async () => {
    await page.waitForTimeout(1500);
    await tap('.ph-big-btn', 700);
    await tap('.ph-arrow >> nth=1', 600);
    await tap('.ph-arrow >> nth=1', 600);
    await tap('.ph-arrow >> nth=0', 700);
    await tap('.ph-menu-card', 900);
    await tap('.ph-item >> text=Entrepreneurship', 900);
    await tap('.ph-item >> text=CitaSalon', 900);
    await scroll(260, 1100);
    await page.waitForTimeout(700);
    await scroll(330, 1100);
    await page.waitForTimeout(1100);
    for (const wait of [700, 700, 900]) await tap('.ph-key-l', wait);
  });
  await browser.close();
  toGif(mp4, path.join(OUT, 'nicos-phone.gif'), { speed: 1.15, width: 300, colors: 32, dither: 'none', fade: ':color=0xc7d6a6' });
}

await desktop();
await phone();
fs.rmSync(TMP, { recursive: true, force: true });
