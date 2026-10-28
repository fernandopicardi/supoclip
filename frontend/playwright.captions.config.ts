import config from "./playwright.polish.config";
export default { ...config, testMatch: ["caption-settings.spec.ts"], workers: 1, timeout: 120_000, webServer: { ...config.webServer, timeout: 180_000 } };
