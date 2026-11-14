import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://127.0.0.1:8123";
const OUT = path.resolve("shots");
const SESSIONS = JSON.parse(
  fs.readFileSync("C:\\Users\\Administrator\\Desktop\\Club\\tools\\sessions.json", "utf8")
);

const PHONE = { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const DESK = { width: 1440, height: 900, deviceScaleFactor: 1 };

const PAGES = [
  ["42-manage-news", "dataentry", "/manage/news/newsarticle/", DESK, false],
  ["44-manage-events", "dataentry", "/manage/events/eventregistration/", DESK, false],
  ["45-manage-mobile", "dataentry", "/manage/", PHONE, false],
  ["56-manage-full", "admin", "/manage/", DESK, true],
  ["57-dashboard-full", "admin", "/dashboard/", DESK, true],
  ["58-home-full", "none", "/", PHONE, true],
  ["59-faq", "none", "/pages/faq/", PHONE, false],
  ["60-about", "none", "/pages/about/", PHONE, false],
  ["61-facilities", "none", "/pages/facilities/", PHONE, false],
  ["62-regulation", "none", "/pages/regulation/", PHONE, false],
  ["63-login-member", "member", "/accounts/login/", PHONE, false],
  ["64-member-renew-full", "member", "/memberships/renew/", PHONE, true],
  ["65-admin-news", "admin", "/manage/news/newsarticle/", DESK, false],
  ["66-admin-events", "admin", "/manage/events/eventregistration/", DESK, false],
  ["67-admin-members", "admin", "/manage/accounts/user/", DESK, false],
  ["68-tournament-detail", "none", "/tournaments/", PHONE, false],
  ["69-course-detail", "none", "/courses/", PHONE, false],
  ["70-trip-detail", "none", "/trips/", PHONE, false],
  ["71-gallery-detail", "none", "/gallery/", PHONE, false],
  ["72-payment-checkout", "member", "/payments/my/", PHONE, false],
];

const run = async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none", "--hide-scrollbars"],
  });

  for (const [name, role, url, viewport, fullPage] of PAGES) {
    const page = await browser.newPage();
    await page.setViewport(viewport);
    if (role !== "none") {
      await page.setCookie({
        name: "sessionid",
        value: SESSIONS[role].sessionid,
        domain: "127.0.0.1",
        path: "/",
        httpOnly: true,
      });
    }
    try {
      const resp = await page.goto(BASE + url, { waitUntil: "networkidle2", timeout: 45000 });
      await new Promise((r) => setTimeout(r, 1200));
      const file = path.join(OUT, `${name}.png`);
      await page.screenshot({ path: file, fullPage });
      console.log(`${name}\t${resp?.status()}\t${page.url()}\t${file}`);
    } catch (e) {
      console.log(`${name}\tERROR\t${e.message}`);
    }
    await page.close();
  }
  await browser.close();
};

run();
