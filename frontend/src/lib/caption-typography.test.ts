import { captionFontUrl, captionPreviewFontSize } from "./caption-typography";

it("keeps the approved 24px setting at 8 percent of frame width", () => {
  expect(captionPreviewFontSize(24)).toBe("8cqw");
  expect(captionPreviewFontSize(12)).toBe("4cqw");
  expect(captionPreviewFontSize(48)).toBe("16cqw");
});

it("requests a fresh, escaped font URL after the bundled font fix", () => {
  expect(captionFontUrl("NunitoSans")).toBe("/api/fonts/NunitoSans?v=20261028-bold-v1");
  expect(captionFontUrl("Custom Font")).toContain("Custom%20Font?");
});
