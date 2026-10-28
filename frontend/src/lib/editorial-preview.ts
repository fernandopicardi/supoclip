import { CaptionLook, CaptionStyle, CaptionWord, DEFAULT_EFFECTS, EditDocument, Framing } from "./editor/document";

export type Cut = { id: string; start: number; end: number };
export type Clip = { id: string; start: number; end: number; cuts: Cut[]; framing?: Framing | null };
export type Montage = { version: 1; source_id: string; title: string; clips: Clip[]; captions: CaptionStyle; framing: Framing; background: "black" | "blur"; word_text: Record<string, string> };
export type PreviewData = { source: { width: number; height: number; duration: number; has_audio: boolean }; words: CaptionWord[]; captionLooks: Record<string, CaptionLook> };
export type Range = { clip: Clip; start: number; end: number; playback: number };

export function montageRanges(doc: Pick<Montage, "clips">): Range[] {
  const ranges: Range[] = [];
  let playback = 0;
  for (const clip of doc.clips) {
    let cursor = clip.start;
    const add = (end: number) => {
      if (end > cursor) { ranges.push({ clip, start: cursor, end, playback }); playback += end - cursor; }
    };
    for (const cut of [...clip.cuts].sort((a, b) => a.start - b.start)) {
      add(Math.min(clip.end, cut.start));
      cursor = Math.max(cursor, cut.end);
    }
    add(clip.end);
  }
  return ranges;
}
export const montageDuration = (ranges: Range[]) => ranges.reduce((n, r) => n + r.end - r.start, 0);
export function playbackTarget(ranges: Range[], time: number) {
  const index = Math.max(0, ranges.findIndex(r => time < r.playback + r.end - r.start));
  const last = ranges.length - 1;
  const i = time >= montageDuration(ranges) ? last : index;
  const range = ranges[i];
  return range ? { index: i, source: range.start + Math.max(0, Math.min(time - range.playback, range.end - range.start)) } : null;
}
export function captionDocument(doc: Montage, words: CaptionWord[], ranges: Range[]): EditDocument {
  const mapped = ranges.flatMap((r, index) => words.flatMap(w => {
    const start = Math.max(r.start, w.start), end = Math.min(r.end, w.end);
    return end > start && end - start >= (w.end - w.start) * .5 ? [{
      ...w, id: `${r.clip.id}:${w.id}:${index}`, start: r.playback + start - r.start, end: r.playback + end - r.start,
      text: doc.word_text[`${r.clip.id}:${w.id}`] ?? w.text,
    }] : [];
  }));
  return { version: 1, segments: [{ id: "playback", start: 0, end: montageDuration(ranges) }], words: mapped,
    captions: doc.captions, framing: doc.framing, effects: DEFAULT_EFFECTS, volume: 1, muted: false };
}
export function montageError(doc: Montage, duration: number) {
  if (!doc.clips.length) return "Inclua pelo menos um trecho antes de salvar.";
  for (const c of doc.clips) {
    if (![c.start, c.end].every(Number.isFinite) || c.start < 0 || c.end <= c.start || c.end > duration + .001)
      return "Confira o início e o fim dos trechos no vídeo original.";
    if (c.cuts.some(t => ![t.start, t.end].every(Number.isFinite) || t.start < c.start || t.end > c.end || t.end <= t.start))
      return "Cada corte interno precisa ficar dentro do seu trecho e terminar depois do início.";
  }
  return montageDuration(montageRanges(doc)) > 0 ? "" : "Os cortes removeram toda a montagem.";
}

/** Mirror the export's even crop/scale/pad geometry at its native output size. */
export function foregroundGeometry(f: Framing, sw: number, sh: number, width: number, height: number) {
  const even = (n: number) => Math.round(n / 2) * 2;
  const scale = (f.fit === "cover" ? Math.max : Math.min)(width / sw, height / sh) * f.zoom;
  const rw = Math.max(f.fit === "cover" ? width : 2, even(sw * scale)), rh = Math.max(2, even(sh * scale));
  const widthOut = Math.min(width, rw), heightOut = Math.min(height, rh);
  const cropWidth = Math.min(sw, Math.max(2, even(widthOut / scale))), cropHeight = Math.min(sh, Math.max(2, even(heightOut / scale)));
  return { sx: Math.max(0, Math.min(sw - cropWidth, even((rw - widthOut) * f.x / scale))),
    sy: Math.max(0, Math.min(sh - cropHeight, even((rh - heightOut) * f.y / scale))),
    sw: cropWidth, sh: cropHeight, width: widthOut, height: heightOut,
    x: Math.floor((width - widthOut) * f.x / 2) * 2, y: Math.floor((height - heightOut) * f.y / 2) * 2 };
}
