import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const BASE = process.argv[2] || "http://127.0.0.1:8080";
const TMP = "C:/Users/Administrator/AppData/Local/Temp/opencode/acceptance";
fs.mkdirSync(TMP, { recursive: true });

// صورة اختبار صغيرة (PNG 1×1)
const imgPath = path.join(TMP, "test-avatar.png");
fs.writeFileSync(imgPath, Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
));

const b = await puppeteer.launch({
  executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  headless: "new",
  args: ["--no-sandbox", "--mute-audio", "--hide-scrollbars"],
});
const p = await b.newPage();
await p.setViewport({ width: 390, height: 844 });
p.on("pageerror", (e) => console.log("  [pageerror]", String(e).slice(0, 140)));

await p.goto(BASE + "/accounts/login/", { waitUntil: "networkidle2" });
await p.type('input[name="phone"]', "01000000001");
await p.type('input[name="password"]', "Demo@12345");
await Promise.all([
  p.waitForNavigation({ waitUntil: "networkidle2" }),
  p.click('form[action*="login"] button[type="submit"], main form button[type="submit"]'),
]);

await p.goto(BASE + "/accounts/profile/edit/", { waitUntil: "networkidle2" });

const info = await p.evaluate(() => {
  const inp = document.querySelector('input[type="file"]');
  if (!inp) return { found: false };
  const r = inp.getBoundingClientRect();
  const cs = getComputedStyle(inp);
  return {
    found: true,
    name: inp.name,
    accept: inp.getAttribute("accept"),
    capture: inp.getAttribute("capture"),
    visible: r.width > 0 && r.height > 0,
    w: Math.round(r.width),
    h: Math.round(r.height),
    display: cs.display,
    visibility: cs.visibility,
    opacity: cs.opacity,
    pointerEvents: cs.pointerEvents,
    formEnctype: inp.form?.getAttribute("enctype"),
  };
});
console.log("حقل الصورة:", JSON.stringify(info));

// ارفع صورة
const input = await p.$('input[type="file"]');
await input.uploadFile(imgPath);
await new Promise((r) => setTimeout(r, 400));

const resp = await Promise.all([
  p.waitForNavigation({ waitUntil: "networkidle2", timeout: 40000 }).catch((e) => console.log("  nav:", e.message.slice(0, 50))),
  p.click('form button[type="submit"]'),
]);
const url = p.url();
const body = await p.evaluate(() => document.body.innerText);
console.log("بعد الحفظ ->", url.replace(BASE, ""));
console.log("رسالة الخطأ :", (body.match(/[^\n]*(خطأ|مطلوب|غير صحيح|بزي)[^\n]*/g) || ["مفيش"]).slice(0, 3).join(" | "));

// هل الصورة اتحفظت؟
const photo = await p.evaluate(() => {
  const img = document.querySelector(".photo-avatar");
  return img ? (img.tagName === "IMG" ? img.getAttribute("src") : "initials") : null;
});
console.log("الصورة دلوقتي:", photo);

await b.close();
