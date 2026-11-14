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

const run = async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none", "--hide-scrollbars"],
  });
  const page = await browser.newPage();
  await page.setViewport(PHONE);
  await page.setCookie({
    name: "sessionid",
    value: SESSIONS.member.sessionid,
    domain: "127.0.0.1",
    path: "/",
    httpOnly: true,
  });

  await page.goto(BASE + "/memberships/renew/", { waitUntil: "networkidle2" });
  await page.click('input[name="beneficiary"][value="self"]');
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: "networkidle2" }).catch(() => {});
  await new Promise((r) => setTimeout(r, 1200));
  console.log("after submit ->", page.url());
  await page.screenshot({ path: path.join(OUT, "26-renew-2.png") });

  // try to reach step 3 (confirmation)
  const hasSubmit = await page.$('button[type="submit"]');
  if (hasSubmit) {
    await page.click('button[type="submit"]');
    await page.waitForNavigation({ waitUntil: "networkidle2" }).catch(() => {});
    await new Promise((r) => setTimeout(r, 1200));
    console.log("after 2nd submit ->", page.url());
    await page.screenshot({ path: path.join(OUT, "26b-renew-3.png") });
  }
  await browser.close();
};

run();
