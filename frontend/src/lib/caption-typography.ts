/** Settings sizes are CSS pixels at a 300px-wide reference frame. */
export const CAPTION_REFERENCE_WIDTH = 300;
export const CAPTION_FONT_REVISION = "20261028-bold-v1";
export const captionFontUrl = (name: string) => `/api/fonts/${encodeURIComponent(name)}?v=${CAPTION_FONT_REVISION}`;

export function captionPreviewFontSize(size: number) {
  return `${size * 100 / CAPTION_REFERENCE_WIDTH}cqw`;
}
