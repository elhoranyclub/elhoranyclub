/**
 * اختبار قبول شامل للموقع — بيمشي على كل الصفحات والتدفّقات لكل دور.
 * التشغيل:  node tools/acceptance/e2e_check.mjs [BASE_URL]
 */
import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.argv[2] || "http://127.0.0.1:8080";
const OUT = path.resolve(process.argv[3] || "C:/Users/Administrator/AppData/Local/Temp/opencode/acceptance");

const results = [];
const log = (...a) => console.log(...a);

function record(group, name, ok, note = "") {
  results.push({ group, name, ok: !!ok, note });
  log(`${ok ? "PASS" : "FAIL"}  [${group}] ${name}${note ? " — " + note : ""}`);
}

const PHONE = { width: 390, height: 844, deviceScaleFactor: 1, isMobile: true, hasTouch: true };
const DESK = { width: 1440, height: 900, deviceScaleFactor: 1 };

async function newPage(browser, viewport = PHONE) {
  const ctx = await browser.createBrowserContext(); // جلسة منفصلة لكل دور
  const page = await ctx.newPage();
  await page.setViewport(viewport);
  page.setDefaultTimeout(25000);
  return page;
}

const goto = (page, url) => page.goto(BASE + url, { waitUntil: "networkidle2", timeout: 30000 });
const textOf = (page) => page.evaluate(() => document.body.innerText);

/** يضغط زرار الإرسال بتاع النموذج الأساسي (مش زرار الخروج في الناف) */
async function submitMainForm(page, needle = "") {
  const clicked = await page.evaluate((needle) => {
    const forms = [...document.querySelectorAll("main form")];
    const form = forms.find((f) => (needle ? f.innerText.includes(needle) : true));
    if (!form) return false;
    const btn = [...form.querySelectorAll("button[type=submit], button:not([type])")].pop();
    if (!btn) return false;
    btn.click();
    return true;
  }, needle);
  if (!clicked) return false;
  await page.waitForNavigation({ waitUntil: "networkidle2" }).catch(() => {});
  await new Promise((r) => setTimeout(r, 900));
  return true;
}

async function login(page, phone, password) {
  await goto(page, "/accounts/login/");
  if (!(await page.$('input[name="phone"]'))) return page.url();
  await page.type('input[name="phone"]', phone);
  await page.type('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2" }).catch(() => {}),
    page.click('form[action*="login"] button[type="submit"], main form button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 600));
  return page.url();
}

const run = async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--mute-audio", "--hide-scrollbars"],
  });

  // ══════════ 1) عامة / زائر ══════════
  {
    const g = "عام (زائر)";
    const page = await newPage(browser);
    const checks = [
      ["/", "الصفحة الرئيسية", "مركز شباب الحوراني"],
      ["/news/", "صفحة الأخبار", "الأخبار"],
      ["/events/", "صفحة الأنشطة", "الأنشطة"],
      ["/tournaments/", "صفحة البطولات", "البطولات"],
      ["/tournaments/live/", "النتائج المباشرة", "مباشر"],
      ["/courses/", "صفحة الدورات", "الدورات"],
      ["/trips/", "صفحة الرحلات", "الرحلات"],
      ["/gallery/", "المعرض", "المعرض"],
      ["/pages/about/", "من نحن", "من نحن"],
      ["/pages/facilities/", "المرافق", "مرافق"],
      ["/pages/pricing/", "الأسعار", "25"],
      ["/pages/regulation/", "لائحة المركز", "لائحة"],
      ["/pages/faq/", "الأسئلة الشائعة", "الأسئلة"],
      ["/pages/contact/", "تواصل معنا", "تواصل"],
    ];
    for (const [url, name, needle] of checks) {
      try {
        const r = await goto(page, url);
        const body = await textOf(page);
        record(g, `${name} (${url})`, r.status() === 200 && body.includes(needle), `status ${r.status()}`);
      } catch (e) {
        record(g, `${name} (${url})`, false, e.message.slice(0, 60));
      }
    }

    // تفاصيل المحتوى
    for (const [listUrl, name, needle] of [
      ["/news/", "تفاصيل خبر", "أخبار"],
      ["/events/", "تفاصيل نشاط", "نشاط"],
      ["/courses/", "تفاصيل دورة", "دورة"],
      ["/trips/", "تفاصيل رحلة", "رحلة"],
      ["/tournaments/", "تفاصيل بطولة", "بطولة"],
    ]) {
      try {
        await goto(page, listUrl);
        const href = await page.evaluate(() => {
          const a = [...document.querySelectorAll("main a[href]")].find((x) =>
            /\/news\/|\/events\/|\/courses\/|\/trips\/|\/tournaments\//.test(x.getAttribute("href") || "") &&
            !/\/(my|enroll|book|register|live)\//.test(x.getAttribute("href") || "") &&
            x.getAttribute("href").split("/").filter(Boolean).length >= 2
          );
          return a ? a.getAttribute("href") : null;
        });
        if (href) {
          const r = await goto(page, href);
          record(g, `${name} (${href})`, r.status() === 200, `status ${r.status()}`);
        } else {
          record(g, name, false, "مفيش لينك تفصيلي");
        }
      } catch (e) { record(g, name, false, e.message.slice(0, 50)); }
    }

    // البحث
    try {
      await goto(page, "/search/?q=%D8%A7%D9%84%D8%A8%D8%B7%D9%88%D9%84%D8%A9");
      const body = await textOf(page);
      record(g, "البحث بيرجّع نتائج", body.includes("نتيجة") || body.includes("نتائج"), body.includes("نتيجة") ? "" : "مفيش كلمة «نتيجة»");
    } catch (e) { record(g, "البحث بيرجّع نتائج", false, e.message); }

    // نموذج التواصل
    try {
      await goto(page, "/pages/contact/");
      await page.type('input[name="name"]', "زائر اختبار");
      await page.type('input[name="phone"]', "01011112222");
      await page.type('input[name="subject"]', "استفسار من الفحص الشامل");
      await page.type('textarea[name="message"]', "رسالة اختبار من الفحص الشامل");
      const ok = await submitMainForm(page);
      const body = await textOf(page);
      record(g, "نموذج التواصل بيبعت رسالة", ok && body.includes("وصلتنا رسالتك"),
        body.includes("وصلتنا رسالتك") ? "" : "الرسالة مرجعتش (تحقق من الحقول)");
    } catch (e) { record(g, "نموذج التواصل بيبعت رسالة", false, e.message.slice(0, 60)); }

    // الدليل التفاعلي (فلترة حسب الدور)
    try {
      await goto(page, "/pages/guide/");
      await new Promise((r) => setTimeout(r, 500));
      const guideInfo = await page.evaluate(() => ({
        role: document.querySelector(".g-role")?.textContent.trim(),
        tabs: [...document.querySelectorAll("#g-tabs button")].map((b) => b.textContent.trim()),
        text: document.querySelector(".g-wrap")?.textContent || "",
      }));
      const leaked = ["القوائم الإدارية", "حسابات التجربة", "قبل النشر", "مدخل بيانات"]
        .filter((w) => guideInfo.text.includes(w));
      record(g, "الدليل التفاعلي للزائر (بدون أقسام إدارية)", leaked.length === 0 && guideInfo.tabs.length === 2,
        leaked.length ? `تسريب: ${leaked.join(", ")}` : `tabs: ${guideInfo.tabs.join(" | ")}`);
    } catch (e) { record(g, "الدليل التفاعلي للزائر", false, e.message.slice(0, 50)); }

    // صفحات النظام
    for (const [url, name, needle] of [
      ["/accounts/login/", "تسجيل الدخول", "رقم الموبايل"],
      ["/accounts/register/", "إنشاء حساب", "إنشاء"],
      ["/offline/", "صفحة بدون إنترنت", ""],
      ["/pages/learn-more/", "صفحة اعرف الموقع أكتر", "اعرف الموقع"],
      ["/sitemap.xml", "خريطة الموقع", "<urlset"],
      ["/robots.txt", "robots.txt", "Sitemap"],
      ["/manifest.webmanifest", "PWA manifest", ""],
      ["/en/", "النسخة الإنجليزية", "Al-Hourani"],
      ["/api/news/?format=json", "API الأخبار (JSON)", "results"],
    ]) {
      try {
        const r = await goto(page, url);
        const body = await textOf(page);
        record(g, `${name} (${url})`, r.status() === 200 && (!needle || body.includes(needle)), `status ${r.status()}`);
      } catch (e) { record(g, `${name} (${url})`, false, e.message.slice(0, 60)); }
    }

    // 404
    try {
      const r = await goto(page, "/صفحة-مش-موجودة-xyz/");
      record(g, "صفحة 404 بتترجم", r.status() === 404, `status ${r.status()}`);
    } catch (e) { record(g, "صفحة 404 بتترجم", false, e.message); }

    // فيديو الدليل
    try {
      await goto(page, "/pages/learn-more/");
      await new Promise((r) => setTimeout(r, 700));
      const info = await page.evaluate(() => ({
        video: !!document.getElementById("guide-video"),
        chapters: document.querySelectorAll(".chapter-btn").length,
        src: document.querySelector("#guide-video source")?.getAttribute("src"),
      }));
      record(g, "صفحة الدليل (زائر) فيها فيديو الزائر", info.video && info.src.includes("/guide/video/guest/") && info.chapters >= 6,
        `${info.chapters} فصل · ${info.src}`);
      const range = await page.evaluate(async () => {
        const res = await fetch("/guide/video/guest/", { headers: { Range: "bytes=0-99" } });
        return { status: res.status, len: (await res.arrayBuffer()).byteLength };
      });
      record(g, "الفيديو بيدعم Range (تنقّل داخل الفيديو)", range.status === 206 && range.len === 100, `status ${range.status}`);
    } catch (e) { record(g, "صفحة الدليل/الفيديو", false, e.message.slice(0, 60)); }

    // حماية الصفحات الإدارية
    for (const [url, name] of [["/manage/", "القوائم الإدارية"], ["/dashboard/", "لوحة التحكم"], ["/admin/", "لوحة Django"]]) {
      try {
        const r = await goto(page, url);
        const body = await textOf(page);
        const hasLoginForm = await page.evaluate(() => !!document.querySelector('input[name="username"], input[name="phone"]'));
        record(g, `${name} محمية من غير تسجيل`, r.status() === 302 || hasLoginForm, `status ${r.status()}`);
      } catch (e) { record(g, `${name} محمية`, false, e.message); }
    }
    await page.close();
  }

  // ══════════ 2) عضو ══════════
  {
    const g = "عضو";
    const page = await newPage(browser);
    const url = await login(page, "01000000001", "Demo@12345");
    record(g, "تسجيل الدخول", !url.includes("login"), `landing: ${url.replace(BASE, "")}`);

    for (const [u, name] of [
      ["/accounts/profile/", "الملف الشخصي"],
      ["/accounts/card/", "كارت العضوية QR"],
      ["/accounts/dependents/", "الأبناء التابعين"],
      ["/accounts/my-services/", "خدماتي"],
      ["/memberships/", "اشتراكاتي"],
      ["/payments/my/", "المدفوعات"],
      ["/notifications/", "الإشعارات"],
      ["/notifications/preferences/", "تفضيلات الإشعارات"],
      ["/courses/my/", "دوراتي"],
      ["/events/my/", "حجوزاتي في الأنشطة"],
      ["/trips/my-bookings/", "رحلاتي"],
      ["/tournaments/my-registrations/", "تسجيلاتي في البطولات"],
      ["/accounts/password-change/", "تغيير كلمة السر"],
      ["/accounts/profile/edit/", "تعديل الملف"],
    ]) {
      try {
        const r = await goto(page, u);
        record(g, `${name} (${u})`, r.status() === 200, `status ${r.status()}`);
      } catch (e) { record(g, `${name} (${u})`, false, e.message.slice(0, 50)); }
    }

    try {
      await goto(page, "/accounts/card/");
      const hasQr = await page.evaluate(() => !!document.querySelector("canvas, img[src*='data:image'], svg"));
      record(g, "كارت العضوية فيه كود QR", hasQr);
    } catch (e) { record(g, "كارت العضوية فيه كود QR", false, e.message); }

    // الفيديو المعروض لعضو = فيديو العضو
    try {
      await goto(page, "/pages/learn-more/");
      const src = await page.evaluate(() => document.querySelector("#guide-video source")?.getAttribute("src"));
      const chapters = await page.$$eval(".chapter-btn", (e) => e.length);
      record(g, "صفحة الدليل تعرض فيديو العضو", !!src && src.includes("/guide/video/member/") && chapters >= 6, `${chapters} فصل · ${src}`);
    } catch (e) { record(g, "صفحة الدليل تعرض فيديو العضو", false, e.message); }

    // الدليل التفاعلي للعضو
    try {
      await goto(page, "/pages/guide/");
      const guideInfo = await page.evaluate(() => ({
        role: document.querySelector(".g-role")?.textContent.trim(),
        text: document.querySelector(".g-wrap")?.textContent || "",
      }));
      const ok = guideInfo.role === "عضو" && guideInfo.text.includes("كارت العضوية") && !guideInfo.text.includes("القوائم الإدارية");
      record(g, "الدليل التفاعلي للعضو (قسم العضو بس)", ok, `role=${guideInfo.role}`);
    } catch (e) { record(g, "الدليل التفاعلي للعضو", false, e.message.slice(0, 50)); }

    // تجديد الاشتراك ٣ خطوات
    try {
      await goto(page, "/memberships/renew/");
      const radios = await page.evaluate(() =>
        [...document.querySelectorAll('input[type=radio]')].map((r) => ({ name: r.name, checked: r.checked }))
      );
      record(g, "تجديد — الخطوة ١ فيها اختيار المستفيد والنوع",
        radios.some((r) => r.name === "beneficiary" && r.checked) && radios.some((r) => r.name === "membership_type" && r.checked));

      await submitMainForm(page, "التالي");
      let body = await textOf(page);
      record(g, "تجديد — الخطوة ٢ (السعر والكوبون)",
        page.url().includes("/renew/2/") && body.includes("25,00"), page.url().replace(BASE, ""));

      await submitMainForm(page, "التالي");
      body = await textOf(page);
      record(g, "تجديد — الخطوة ٣ (التأكيد/الدفع)",
        page.url().includes("/renew/3/") || page.url().includes("/checkout/"), page.url().replace(BASE, ""));

      // الدفع وهمي → الإيصال
      if (page.url().includes("/checkout/")) {
        const paid = await submitMainForm(page, "ادفع");
        body = await textOf(page);
        record(g, "الدفع (mock) بيوصّل لصفحة الإيصال", paid && (body.includes("إيصال") || body.includes("تم") || page.url().includes("/receipt/")), page.url().replace(BASE, ""));
      }
    } catch (e) { record(g, "تدفّق تجديد الاشتراك", false, e.message.slice(0, 70)); }

    // تسجيل في دورة
    try {
      await goto(page, "/courses/");
      const href = await page.evaluate(() => {
        const a = [...document.querySelectorAll("main a[href*='/courses/']")].find((x) => {
          const h = x.getAttribute("href") || "";
          return h.split("/").filter(Boolean).length === 2 && !h.includes("/my/");
        });
        return a ? a.getAttribute("href") : null;
      });
      if (href) {
        await goto(page, href);
        const enroll = await page.evaluate(() => {
          const a = [...document.querySelectorAll("main a[href*='/enroll/']")][0];
          return a ? a.getAttribute("href") : null;
        });
        if (enroll) {
          await goto(page, enroll);
          record(g, "صفحة تسجيل في دورة", page.url().includes("/enroll/"), page.url().replace(BASE, ""));
        } else record(g, "صفحة تسجيل في دورة", true, "مفيش دورة مفتوحة للتسجيل");
      } else record(g, "صفحة تسجيل في دورة", false, "مفيش دورات");
    } catch (e) { record(g, "صفحة تسجيل في دورة", false, e.message.slice(0, 50)); }

    // الإشعارات
    try {
      await goto(page, "/notifications/");
      const body = await textOf(page);
      record(g, "صفحة الإشعارات فيها بنود", body.length > 100, `${body.length} حرف`);
    } catch (e) { record(g, "صفحة الإشعارات", false, e.message); }

    try {
      await goto(page, "/accounts/logout/");
      record(g, "تسجيل الخروج", (await textOf(page)).includes("تسجيل خروجك"));
    } catch (e) { record(g, "تسجيل الخروج", false, e.message); }
    await page.close();
  }

  // ══════════ 3) مدخل بيانات ══════════
  {
    const g = "مدخل البيانات";
    const page = await newPage(browser, DESK);
    const url = await login(page, "01099990000", "Demo@12345");
    record(g, "تسجيل الدخول", !url.includes("login"), url.replace(BASE, ""));

    for (const [u, name, needle] of [
      ["/manage/", "القوائم الإدارية", "القوائم"],
      ["/manage/news/newsarticle/", "إدارة الأخبار", ""],
      ["/manage/events/eventregistration/", "تسجيلات الأنشطة", ""],
      ["/manage/courses/course/", "إدارة الدورات", ""],
      ["/manage/trips/trip/", "إدارة الرحلات", ""],
      ["/manage/tournaments/tournament/", "إدارة البطولات", ""],
      ["/manage/memberships/membership/", "إدارة الاشتراكات", ""],
      ["/dashboard/", "لوحة التحكم (staff)", "لوحة"],
    ]) {
      try {
        const r = await goto(page, u);
        const body = await textOf(page);
        record(g, `${name} (${u})`, r.status() === 200 && (!needle || body.includes(needle)), `status ${r.status()}`);
      } catch (e) { record(g, `${name} (${u})`, false, e.message.slice(0, 50)); }
    }

    // إضافة خبر من شاشة الإدارة
    try {
      await goto(page, "/manage/news/newsarticle/new/");
      const hasForm = await page.evaluate(() => !!document.querySelector("main form"));
      record(g, "شاشة إضافة خبر موجودة", hasForm);
    } catch (e) { record(g, "شاشة إضافة خبر", false, e.message.slice(0, 50)); }

    // لازم ما يدخلش /admin/
    try {
      await goto(page, "/admin/");
      const loggedIn = await page.evaluate(() => !!document.querySelector('a[href*="/logout/"]'));
      record(g, "مفيش دخول للوحة Django (السوبر أدمن بس)", !loggedIn, loggedIn ? "دخل! " : "ظهر فورم الدخول");
    } catch (e) { record(g, "مفيش دخول للوحة Django", false, e.message); }

    // الفيديو المعروض لمدخل البيانات = فيديو مدخل البيانات
    try {
      await goto(page, "/pages/learn-more/");
      const src = await page.evaluate(() => document.querySelector("#guide-video source")?.getAttribute("src"));
      record(g, "صفحة الدليل تعرض فيديو مدخل البيانات", !!src && src.includes("/guide/video/dataentry/"), src);
    } catch (e) { record(g, "صفحة الدليل تعرض فيديو مدخل البيانات", false, e.message); }

    // الدليل التفاعلي لمدخل البيانات
    try {
      await goto(page, "/pages/guide/");
      const guideInfo = await page.evaluate(() => ({
        role: document.querySelector(".g-role")?.textContent.trim(),
        text: document.querySelector(".g-wrap")?.textContent || "",
      }));
      const ok = guideInfo.role === "مدخل بيانات" && guideInfo.text.includes("القوائم الإدارية") && !guideInfo.text.includes("حسابات التجربة");
      record(g, "الدليل التفاعلي لمدخل البيانات (بلا أقسام الإدارة)", ok, `role=${guideInfo.role}`);
    } catch (e) { record(g, "الدليل التفاعلي لمدخل البيانات", false, e.message.slice(0, 50)); }
    await page.close();
  }

  // ══════════ 4) أدمن ══════════
  {
    const g = "الإدارة";
    const page = await newPage(browser, DESK);
    const url = await login(page, "01000000009", "Admin@12345");
    record(g, "تسجيل الدخول", !url.includes("login"), url.replace(BASE, ""));

    for (const [u, name, needle] of [
      ["/dashboard/", "لوحة التحكم", "لوحة"],
      ["/manage/", "القوائم الإدارية (كامل)", "القوائم"],
      ["/admin/", "لوحة Django", "لوحة"],
      ["/payments/staff/", "مراجعة المدفوعات", ""],
    ]) {
      try {
        const r = await goto(page, u);
        const body = await textOf(page);
        record(g, `${name} (${u})`, r.status() === 200 && (!needle || body.includes(needle)), `status ${r.status()}`);
      } catch (e) { record(g, `${name} (${u})`, false, e.message.slice(0, 50)); }
    }

    for (const [u, name] of [["/dashboard/export/members.csv", "تصدير الأعضاء CSV"], ["/dashboard/export/payments.csv", "تصدير المدفوعات CSV"]]) {
      try {
        const res = await page.evaluate(async (url) => {
          const r = await fetch(url, { credentials: "same-origin" });
          const text = await r.text();
          return { status: r.status, type: r.headers.get("content-type") || "", head: text.slice(0, 40) };
        }, u);
        record(g, `${name} (${u})`, res.status === 200 && res.type.includes("csv"), `status ${res.status} · ${res.type}`);
      } catch (e) { record(g, `${name}`, false, e.message.slice(0, 50)); }
    }

    try {
      await goto(page, "/admin/");
      const hasSettings = await page.evaluate(() =>
        [...document.querySelectorAll("a")].some((a) => (a.getAttribute("href") || "").includes("site"))
      );
      record(g, "إعدادات الموقع متاحة من /admin/", hasSettings);
    } catch (e) { record(g, "إعدادات الموقع", false, e.message); }

    // الفيديو المعروض للإدارة = فيديو الإدارة
    try {
      await goto(page, "/pages/learn-more/");
      const src = await page.evaluate(() => document.querySelector("#guide-video source")?.getAttribute("src"));
      record(g, "صفحة الدليل تعرض فيديو الإدارة", !!src && src.includes("/guide/video/admin/"), src);
    } catch (e) { record(g, "صفحة الدليل تعرض فيديو الإدارة", false, e.message); }

    // الدليل التفاعلي للإدارة — كل الأقسام
    try {
      await goto(page, "/pages/guide/");
      const guideInfo = await page.evaluate(() => ({
        role: document.querySelector(".g-role")?.textContent.trim(),
        tabs: document.querySelectorAll("#g-tabs button").length,
        text: document.querySelector(".g-wrap")?.textContent || "",
      }));
      const ok = guideInfo.role === "الإدارة" && guideInfo.tabs === 7 && guideInfo.text.includes("حسابات التجربة");
      record(g, "الدليل التفاعلي للإدارة (كل الأقسام)", ok, `${guideInfo.tabs} تبويب`);
    } catch (e) { record(g, "الدليل التفاعلي للإدارة", false, e.message.slice(0, 50)); }
    await page.close();
  }

  await browser.close();

  // ══════════ التقرير ══════════
  const passed = results.filter((r) => r.ok).length;
  const failed = results.filter((r) => !r.ok);
  const byGroup = {};
  for (const r of results) {
    byGroup[r.group] = byGroup[r.group] || { pass: 0, fail: 0 };
    byGroup[r.group][r.ok ? "pass" : "fail"]++;
  }
  let md = `# تقرير الاختبار الشامل — مركز شباب الحوراني\n\n`;
  md += `- **التاريخ:** ${new Date().toISOString().slice(0, 16).replace("T", " ")}\n`;
  md += `- **الرابط المختبَر:** ${BASE}\n`;
  md += `- **النتيجة:** ${passed}/${results.length} ناجح`;
  md += failed.length ? ` — **${failed.length} فاشل**\n\n` : " — كله تمام ✅\n\n";
  md += `| المجموعة | ناجح | فاشل |\n|---|---|---|\n`;
  for (const [grp, v] of Object.entries(byGroup)) md += `| ${grp} | ${v.pass} | ${v.fail} |\n`;
  if (failed.length) {
    md += `\n## ❌ اللي فاشل\n\n`;
    for (const f of failed) md += `- **[${f.group}]** ${f.name} ${f.note ? `— ${f.note}` : ""}\n`;
  }
  md += `\n## ✅ كل الاختبارات\n\n`;
  let cur = "";
  for (const r of results) {
    if (r.group !== cur) { cur = r.group; md += `\n### ${cur}\n\n`; }
    md += `- ${r.ok ? "✅" : "❌"} ${r.name}${r.note ? ` _(${r.note})_` : ""}\n`;
  }
  fs.writeFileSync(path.join(OUT, "acceptance_report.md"), md, "utf8");
  fs.writeFileSync(path.join(OUT, "acceptance_results.json"), JSON.stringify(results, null, 2), "utf8");
  log(`\n===== ${passed}/${results.length} ناجح =====`);
  if (failed.length) log("فاشل:\n" + failed.map((f) => `  - [${f.group}] ${f.name} ${f.note}`).join("\n"));
};

run();
