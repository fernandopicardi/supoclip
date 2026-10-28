import config from "./playwright.polish.config";
export default { ...config, testMatch: ["editorial-preview.spec.ts"], workers: 1, timeout: 120_000, use: { ...config.use, actionTimeout: 20_000 }, webServer: { ...config.webServer, timeout: 180_000 } };
