import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("montage preview saves explicitly, preserves conflicts and never exports automatically", async ({ page }) => {
  const framing = { aspect: "vertical", fit: "contain", zoom: 1, x: .5, y: .5 };
  let edit = { edit_id: "edit_test", revision: 3, exports: [], document: { version: 1, source_id: "source_test", title: "Montagem de teste", background: "black", framing,
    captions: { enabled: true, font: "NunitoSans", size: 118, color: "#FFFFFF", accent: "#D6F777", y: .2, background: false, wordsPerLine: 3, karaoke: true, uppercase: false, template: "default" },
    clips: [{ id: "a", start: 0, end: 2, cuts: [] }, { id: "b", start: 3, end: 5, cuts: [] }], word_text: {} } };
  const words = [{ id: "w1", start: .1, end: .8, text: "Sua", highlight: false }, { id: "w2", start: .9, end: 1.8, text: "legenda", highlight: false }, { id: "w3", start: 3.1, end: 4.7, text: "teste", highlight: false }];
  let writes = 0, exports = 0, conflict = false;
  const media = process.env.SUPOCLIP_TEST_EXISTING_MEDIA ? readFileSync(process.env.SUPOCLIP_TEST_EXISTING_MEDIA) : null;
  page.on("request", request => { if (request.method() === "POST" && request.url().includes("/exports")) exports++; });
  await page.route("**/api/auth/get-session**", route => route.fulfill({ json: { session: { id: "session", userId: "user", expiresAt: "2099-01-01T00:00:00Z" }, user: { id: "user", name: "Teste", email: "test@example.com", emailVerified: true } } }));
  await page.route("**/api/announcements**", route => route.fulfill({ json: { announcements: [] } }));
  await page.route("**/api/tasks/billing-summary", route => route.fulfill({ json: { monetization_enabled: false } }));
  await page.route("**/api/fonts", route => route.fulfill({ json: { fonts: [{ name: "NunitoSans", display_name: "Nunito Sans" }] } }));
  await page.route("**/api/fonts/NunitoSans?**", route => route.fulfill({ contentType: "font/ttf", body: readFileSync("../backend/fonts/NunitoSans.ttf") }));
  await page.route("**/api/editorial/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/media")) {
      // Optional existing local recording; this test never invokes an encoder.
      if (media) {
        const range = /^bytes=(\d+)-(\d*)$/.exec(route.request().headers().range || "");
        const start = range ? Number(range[1]) : 0, end = range?.[2] ? Math.min(media.length - 1, Number(range[2])) : media.length - 1;
        await route.fulfill({ status: range ? 206 : 200, contentType: "video/mp4", body: media.subarray(start, end + 1),
          headers: { "Accept-Ranges": "bytes", ...(range ? { "Content-Range": `bytes ${start}-${end}/${media.length}` } : {}) } });
      }
      else await route.fulfill({ status: 404 });
    } else if (url.pathname.endsWith("/preview-data")) await route.fulfill({ json: { source: { width: 1280, height: 720, duration: 60, has_audio: true }, words, captionLooks: {} } });
    else if (url.pathname.endsWith("/draft")) {
      if (conflict) { await route.fulfill({ status: 409, json: { detail: "Changed" } }); return; }
      const body = route.request().postDataJSON();
      expect(body.revision).toBe(edit.revision);
      edit = { ...edit, revision: edit.revision + 1, document: body.document }; writes++;
      await route.fulfill({ json: edit });
    } else await route.fulfill({ json: edit });
  });
  await page.goto("/editorial/edit_test");
  await expect(page.getByRole("heading", { name: "Montagem de teste" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Salvar montagem", exact: true })).toBeDisabled();
  await page.getByRole("combobox", { name: "Fundo do vídeo", exact: true }).selectOption("blur");
  await page.getByRole("button", { name: /^(Center|Centro)$/ }).click();
  await page.getByRole("button", { name: "Subir trecho 2" }).click();
  await page.getByLabel("Fim do trecho 1 (s)", { exact: true }).fill("4.8");
  await page.getByText("Corrigir texto da legenda", { exact: true }).first().click();
  await page.getByLabel("Legenda em 3.10s do trecho 1", { exact: true }).fill("corrigida");
  await expect(page.getByRole("button", { name: "Exportar versão salva" })).toBeDisabled();
  expect(writes).toBe(0);
  await page.getByRole("button", { name: "Salvar montagem", exact: true }).click();
  await expect.poll(() => writes).toBe(1);
  expect(edit.document.background).toBe("blur"); expect(edit.document.captions.y).toBe(.5);
  expect(edit.document.clips[0].id).toBe("b"); expect(edit.document.clips[0].end).toBe(4.8);
  expect(edit.document.word_text).toEqual({ "b:w3": "corrigida" });
  await expect(page.getByRole("button", { name: "Exportar versão salva" })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Fundo do vídeo", exact: true })).toHaveValue("blur");
  if (process.env.SUPOCLIP_TEST_EXISTING_MEDIA) {
    await expect(page.getByRole("button", { name: "Reproduzir", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Reproduzir", exact: true }).click();
    await expect.poll(() => page.locator('video[aria-hidden="true"]').evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(3.3);
    await expect(page.getByRole("button", { name: "Pausar", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Pausar", exact: true }).click();
    // Scrub into the second occurrence, so source image and captions use its clock.
    await page.getByRole("slider", { name: "Posição na montagem" }).focus();
    await page.keyboard.press("End");
    await expect.poll(() => page.locator('video[aria-hidden="true"]').evaluate((v: HTMLVideoElement) => v.seeking)).toBe(false);
    await page.keyboard.press("ArrowLeft");
    await expect.poll(() => page.locator('video[aria-hidden="true"]').evaluate((v: HTMLVideoElement) => v.currentTime)).toBeCloseTo(1.99, 1);
  }
  await page.screenshot({ path: "test-results/editorial-preview-desktop.png", fullPage: true });
  conflict = true;
  await page.getByLabel("Tamanho da legenda", { exact: true }).fill("140");
  await page.getByRole("button", { name: "Salvar montagem", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "outra sessão" })).toBeVisible();
  await expect(page.getByLabel("Tamanho da legenda", { exact: true })).toHaveValue("140");
  await expect(page.getByRole("button", { name: "Exportar versão salva" })).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/editorial-preview-mobile.png", fullPage: true });
  expect(exports).toBe(0);
});
