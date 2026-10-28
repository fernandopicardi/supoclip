import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("caption controls preview, save and reload without creating media", async ({ page }) => {
  let prefs = { fontFamily: "NunitoSans", fontSize: 24, fontColor: "#FFFFFF", notifyOnCompletion: true,
    captionStyle: { y: .78, wordsPerLine: 4, background: false, uppercase: false, karaoke: false, accent: "#D6F777" } };
  let writes = 0;
  let mediaRequests = 0;
  page.on("request", request => { if (/\/tasks\/create|\/exports/.test(request.url())) mediaRequests++; });
  await page.route("**/api/auth/get-session**", route => route.fulfill({ json: {
    session: { id: "session", userId: "user", expiresAt: "2099-01-01T00:00:00Z" },
    user: { id: "user", name: "Teste", email: "test@example.com", emailVerified: true } } }));
  await page.route("**/api/fonts", route => route.fulfill({ json: { fonts: [{ name: "NunitoSans", display_name: "Nunito Sans", scope: "system" }] } }));
  await page.route("**/api/fonts/NunitoSans?**", route => route.fulfill({ contentType: "font/ttf", body: readFileSync("../backend/fonts/NunitoSans.ttf") }));
  await page.route("**/api/announcements**", route => route.fulfill({ json: { announcements: [] } }));
  await page.route("**/api/tasks/billing-summary", route => route.fulfill({ json: { monetization_enabled: false } }));
  await page.route("**/api/preferences", async route => {
    if (route.request().method() === "PATCH") { prefs = { ...prefs, ...route.request().postDataJSON() }; writes++; }
    await route.fulfill({ json: prefs });
  });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Caption defaults" })).toBeVisible();
  await page.getByRole("button", { name: "Center", exact: true }).click();
  const drag = page.getByRole("button", { name: "Drag the caption or use arrow keys to adjust its position" });
  await expect(drag).toHaveAttribute("style", /top: 50%/);
  await expect(drag).toHaveCSS("font-size", "12px");
  await expect(drag).toHaveCSS("font-weight", "700");
  await page.evaluate(() => document.fonts.ready);
  await drag.focus();
  await page.keyboard.press("Shift+ArrowUp");
  await expect(page.getByText("45%", { exact: true })).toBeVisible();
  await page.getByLabel("Words per caption", { exact: true }).fill("3");
  await page.getByRole("switch", { name: "Contrast background", exact: true }).click();
  await page.getByRole("switch", { name: "Highlight the spoken word", exact: true }).click();
  await page.getByRole("button", { name: /^Save preferences$/i }).click();
  await expect.poll(() => writes).toBe(1);
  expect(prefs.captionStyle).toMatchObject({ y: .45, wordsPerLine: 3, background: true, karaoke: true });
  expect(prefs.fontFamily).toBe("NunitoSans");
  expect(prefs.fontSize).toBe(24);
  await page.reload();
  await expect(page.getByText("45%", { exact: true })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Contrast background", exact: true })).toBeChecked();
  const box = await drag.boundingBox();
  const frame = await page.getByLabel("Caption preview", { exact: true }).boundingBox();
  if (!box || !frame) throw new Error("Caption preview has no bounds");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(frame.x + frame.width / 2, frame.y + frame.height * .6, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByText("60%", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/caption-settings-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Center", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/caption-settings-mobile.png", fullPage: true });
  expect(mediaRequests).toBe(0);
});
