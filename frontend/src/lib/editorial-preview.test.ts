import { describe, expect, it } from "vitest";
import { captionDocument, foregroundGeometry, Montage, montageDuration, montageError, montageRanges, playbackTarget } from "./editorial-preview";

const framing = { aspect: "vertical" as const, fit: "contain" as const, zoom: 2.55, x: .53, y: .5 };
const doc: Montage = { version: 1, source_id: "source", title: "Teste", background: "blur", framing,
  captions: { enabled: true, font: "NunitoSans", size: 118, color: "#FFFFFF", accent: "#D6F777", y: .2, background: false, wordsPerLine: 3 },
  clips: [{ id: "late", start: 10, end: 14, cuts: [{ id: "cut", start: 11, end: 12 }] }, { id: "repeat", start: 10, end: 11, cuts: [] }],
  word_text: { "late:w": "corrigida" } };
describe("montage preview uses source time and occurrence corrections", () => {
  it("subtracts overlapping cuts and seeks across reordered and repeated ranges", () => {
    const ranges = montageRanges(doc);
    expect(ranges.map(r => [r.start, r.end, r.playback])).toEqual([[10, 11, 0], [12, 14, 1], [10, 11, 3]]);
    expect(montageDuration(ranges)).toBe(4);
    expect(playbackTarget(ranges, 1)).toEqual({ index: 1, source: 12 });
    expect(playbackTarget(ranges, 3.5)).toEqual({ index: 2, source: 10.5 });
    expect(playbackTarget(ranges, 4)).toEqual({ index: 2, source: 11 });
    const overlapping = structuredClone(doc); overlapping.clips[0].cuts.push({ id: "overlap", start: 11.5, end: 13 });
    expect(montageDuration(montageRanges(overlapping))).toBe(3);
  });
  it("maps captions with the same half-word rule as export, preserving repeated occurrences", () => {
    const captions = captionDocument(doc, [{ id: "w", start: 10.1, end: 10.5, text: "original", highlight: false },
      { id: "removed", start: 11.2, end: 11.7, text: "cortada", highlight: false }], montageRanges(doc));
    expect(captions.words.map(w => [w.text, Number(w.start.toFixed(2))])).toEqual([["corrigida", .1], ["original", 3.1]]);
    expect(captions.captions.size).toBe(118);
    expect(montageError(doc, 15)).toBe("");
    const invalid = structuredClone(doc); invalid.clips[0].start = 12;
    expect(montageError(invalid, 15)).toContain("corte interno");
  });
  it("matches the exported foreground instead of enlarging the entire original", () => {
    const g = foregroundGeometry(framing, 1280, 720, 720, 1280);
    expect(g.height).toBe(1032); expect(g.y).toBe(124); expect(g.width).toBe(720);
    expect(g.sw).toBe(502); expect(g.sx % 2).toBe(0);
  });
});
