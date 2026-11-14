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
  // name, role, url, viewport, fullPage
  ["01-home", "none", "/", PHONE, false],
  ["02-news", "none", "/news/", PHONE, false],
  ["03-tournaments", "none", "/tournaments/", PHONE, false],
  ["04-tournaments-live", "none", "/tournaments/live/", PHONE, false],
  ["05-courses", "none", "/courses/", PHONE, false],
  ["06-trips", "none", "/trips/", PHONE, false],
  ["07-gallery", "none", "/gallery/", PHONE, false],
  ["08-contact", "none", "/pages/contact/", PHONE, false],
  ["09-pricing", "none", "/pages/pricing/", PHONE, false],
  ["10-register", "none", "/accounts/register/", PHONE, false],
  ["11-login", "none", "/accounts/login/", PHONE, false],

  ["20-member-home", "member", "/", PHONE, false],
  ["21-member-services", "member", "/accounts/my-services/", PHONE, false],
  ["22-member-card", "member", "/accounts/card/", PHONE, false],
  ["23-member-profile", "member", "/accounts/profile/", PHONE, false],
  ["24-member-dependents", "member", "/accounts/dependents/", PHONE, false],
  ["25-renew-1", "member", "/memberships/renew/", PHONE, false],
  ["26-renew-2", "member", "/memberships/renew/2/", PHONE, false],
  ["27-notifications", "member", "/notifications/", PHONE, false],
  ["28-member-payments", "member", "/payments/my/", PHONE, false],
  ["29-member-courses", "member", "/courses/my/", PHONE, false],

  ["40-manage-index", "dataentry", "/manage/", DESK, false],
  ["41-manage-index-mobile", "dataentry", "/manage/", PHONE, false],
  ["42-manage-news", "dataentry", "/manage/news/article/", DESK, false],
  ["43-manage-news-mobile", "dataentry", "/manage/news/article/", PHONE, false],

  ["50-dashboard", "admin", "/dashboard/", DESK, false],
  ["51-dashboard-mobile", "admin", "/dashboard/", PHONE, false],
  ["52-admin-index", "admin", "/admin/", DESK, false],
  ["53-manage-admin", "admin", "/manage/", DESK, false],
  ["54-manage-admin-mobile", "admin", "/manage/", PHONE, false],
  ["55-payments-review", "admin", "/payments/staff/", DESK, false],
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
      const title = await page.title();
      console.log(`${name}\t${resp?.status()}\t${title}\t${file}`);
    } catch (e) {
      console.log(`${name}\tERROR\t${e.message}`);
    }
    await page.close();
  }
  await browser.close();
};

run();
