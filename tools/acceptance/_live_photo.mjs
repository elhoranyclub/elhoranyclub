import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const BASE = process.argv[2] || "https://elhoranyclub.onrender.com";
const TMP = "C:/Users/Administrator/AppData/Local/Temp/opencode/acceptance";
fs.mkdirSync(TMP, { recursive: true });
const imgPath = path.join(TMP, "live-avatar.png");
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
p.on("pageerror", (e) => console.log("  [pageerror]", String(e).slice(0, 120)));

await p.goto(BASE + "/accounts/login/", { waitUntil: "networkidle2", timeout: 90000 });
await p.type('input[name="phone"]', "01000000001");
await p.type('input[name="password"]', "Demo@12345");
await Promise.all([
  p.waitForNavigation({ waitUntil: "networkidle2", timeout: 90000 }).catch(() => {}),
  p.click('form[action*="login"] button[type="submit"], main form button[type="submit"]'),
]);
await new Promise((r) => setTimeout(r, 1500));
console.log("1) بعد الدخول ->", p.url());

if (p.url().includes("/accounts/login")) {
  console.log("   (!) الحساب مش موجود على الإنتاج — شغّل ensure_demo_accounts في Shell");
} else {
  await p.goto(BASE + "/accounts/profile/edit/", { waitUntil: "networkidle2", timeout: 90000 });
  const input = await p.$('input[type="file"]');
  if (input) {
    await input.uploadFile(imgPath);
    await Promise.all([
      p.waitForNavigation({ waitUntil: "networkidle2", timeout: 90000 }).catch((e) => console.log("  nav:", e.message.slice(0, 40))),
      p.click('form button[type="submit"]'),
    ]);
    await new Promise((r) => setTimeout(r, 1500));
    console.log("2) بعد الحفظ ->", p.url().replace(BASE, ""));
    const body = await p.evaluate(() => document.body.innerText);
    const errs = (body.match(/[^\n]*(خطأ|Error|مش قادر|جرب)[^\n]*/g) || []).slice(0, 2);
    console.log("   أخطاء:", errs.join(" | ") || "مفيش");

    // الصورة ظهرت في صفحة الحساب؟
    await p.goto(BASE + "/accounts/profile/", { waitUntil: "networkidle2", timeout: 90000 });
    const img = await p.evaluate(() => {
      const el = document.querySelector(".mcard-photo") || document.querySelector(".photo-avatar");
      if (!el) return "مفيش عنصر";
      if (el.tagName !== "IMG") return "initials (الصورة مش متحملة)";
      return el.getAttribute("src");
    });
    console.log("3) الصورة في صفحة الحساب:", img);
    if (img && img.startsWith("http")) {
      const r = await fetch(img).catch((e) => null);
      console.log("   حالة صورة الملف:", r ? r.status : "ERR");
    }
  }
}
await b.close();
