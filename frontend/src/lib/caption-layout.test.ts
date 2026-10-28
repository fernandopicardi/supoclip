import { clampCaptionPosition, DEFAULT_CAPTION_LAYOUT, parseCaptionLayout, savedCaptionLayout } from "./caption-layout";

it("keeps a complete serializable caption layout and false values", () => {
  const parsed = parseCaptionLayout({ y: 0.5, background: false, karaoke: false, wordsPerLine: 2 });
  expect(parsed).toEqual({ ...DEFAULT_CAPTION_LAYOUT, y: 0.5, wordsPerLine: 2 });
  expect(savedCaptionLayout(JSON.parse(JSON.stringify(parsed)))).toEqual(parsed);
});

it.each([{ y: 0 }, { y: 1 }, { y: true }, { wordsPerLine: 0 }, { wordsPerLine: 1.5 }, { background: "false" }, { unknown: true }, null])("rejects invalid caption layouts: %j", (value) => {
  expect(() => parseCaptionLayout(value)).toThrow();
});

it("clamps pointer positions to safe bounds without losing fine adjustment", () => {
  expect(clampCaptionPosition(-20)).toBe(0.1);
  expect(clampCaptionPosition(120)).toBe(0.9);
  expect(clampCaptionPosition(51)).toBe(0.51);
});
