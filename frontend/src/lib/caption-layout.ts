export const DEFAULT_CAPTION_LAYOUT = {
  y: 0.78,
  wordsPerLine: 4,
  background: false,
  uppercase: false,
  karaoke: false,
  accent: "#D6F777",
};

export type CaptionLayout = typeof DEFAULT_CAPTION_LAYOUT;

export function parseCaptionLayout(value: unknown): CaptionLayout {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid captionStyle");
  const input = value as Record<string, unknown>;
  if (Object.keys(input).some((key) => !(key in DEFAULT_CAPTION_LAYOUT))) throw new Error("Unknown captionStyle option");
  const result = { ...DEFAULT_CAPTION_LAYOUT, ...input };
  if (typeof result.y !== "number" || !Number.isFinite(result.y) || result.y < 0.1 || result.y > 0.9) throw new Error("Invalid caption position (10–90%)");
  if (typeof result.wordsPerLine !== "number" || !Number.isInteger(result.wordsPerLine) || result.wordsPerLine < 1 || result.wordsPerLine > 8) throw new Error("Invalid wordsPerLine (1–8)");
  for (const key of ["background", "uppercase", "karaoke"] as const) {
    if (typeof result[key] !== "boolean") throw new Error(`Invalid captionStyle.${key}`);
  }
  if (typeof result.accent !== "string" || !/^#[\da-f]{6}$/i.test(result.accent)) throw new Error("Invalid caption accent color");
  return result as CaptionLayout;
}

export function savedCaptionLayout(value: unknown): CaptionLayout {
  try { return parseCaptionLayout(value ?? {}); } catch { return { ...DEFAULT_CAPTION_LAYOUT }; }
}

export function clampCaptionPosition(value: number) {
  return Math.round(Math.min(90, Math.max(10, value)) * 100) / 10000;
}
