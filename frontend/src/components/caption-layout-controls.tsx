"use client";

import { useId, useRef } from "react";
import { useLocale } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { clampCaptionPosition, type CaptionLayout } from "@/lib/caption-layout";
import { captionPreviewFontSize } from "@/lib/caption-typography";

const labels = {
  pt: { position: "Posição da legenda", top: "Alto", center: "Centro", bottom: "Baixo", words: "Palavras por legenda", background: "Fundo para contraste", uppercase: "Texto em maiúsculas", karaoke: "Destacar a palavra falada", accent: "Cor do destaque", drag: "Arraste a legenda ou use as setas para ajustar a posição", sample: "Sua legenda vai ficar assim", safe: "Margem para os botões das redes", preview: "Prévia da legenda" },
  en: { position: "Caption position", top: "Top", center: "Center", bottom: "Bottom", words: "Words per caption", background: "Contrast background", uppercase: "Uppercase text", karaoke: "Highlight the spoken word", accent: "Highlight color", drag: "Drag the caption or use arrow keys to adjust its position", sample: "Your captions will look like this", safe: "Space for social app controls", preview: "Caption preview" },
};

function useLabels() { return labels[useLocale().startsWith("pt") ? "pt" : "en"]; }

export function CaptionLayoutControls({ value, onChange, disabled = false }: { value: CaptionLayout; onChange: (value: CaptionLayout) => void; disabled?: boolean }) {
  const text = useLabels();
  const id = useId();
  const update = (patch: Partial<CaptionLayout>) => onChange({ ...value, ...patch });
  return <div className="space-y-5">
    <div className="space-y-3">
      <div className="flex items-center justify-between"><Label>{text.position}</Label><span className="text-xs tabular-nums text-muted-foreground">{Math.round(value.y * 100)}%</span></div>
      <div className="grid grid-cols-3 gap-2">
        {([{ label: text.top, y: 0.2 }, { label: text.center, y: 0.5 }, { label: text.bottom, y: 0.78 }]).map((preset) => <Button key={preset.y} type="button" variant={Math.abs(value.y - preset.y) < 0.005 ? "default" : "outline"} size="sm" disabled={disabled} aria-pressed={Math.abs(value.y - preset.y) < 0.005} onClick={() => update({ y: preset.y })}>{preset.label}</Button>)}
      </div>
      <Slider value={[value.y * 100]} min={10} max={90} step={1} disabled={disabled} aria-label={text.position} onValueChange={([y]) => update({ y: clampCaptionPosition(y) })} />
    </div>
    <div className="flex items-center justify-between gap-3"><Label htmlFor={`${id}-caption-word-count`}>{text.words}</Label><Input id={`${id}-caption-word-count`} className="h-8 w-20" type="number" min={1} max={8} disabled={disabled} value={value.wordsPerLine} onChange={(event) => { const n = Number(event.target.value); if (Number.isInteger(n) && n >= 1 && n <= 8) update({ wordsPerLine: n }); }} /></div>
    {(["background", "uppercase", "karaoke"] as const).map((key) => <div key={key} className="flex items-center justify-between gap-3"><Label htmlFor={`${id}-caption-${key}`}>{text[key]}</Label><Switch id={`${id}-caption-${key}`} checked={value[key]} onCheckedChange={(checked) => update({ [key]: checked })} disabled={disabled} /></div>)}
    {value.karaoke && <div className="flex items-center justify-between gap-3"><Label htmlFor={`${id}-caption-accent`}>{text.accent}</Label><input id={`${id}-caption-accent`} className="h-8 w-12 cursor-pointer" type="color" value={value.accent} disabled={disabled} onChange={(event) => update({ accent: event.target.value })} /></div>}
  </div>;
}

export function CaptionStylePreview({ value, onChange, fontFamily, fontSize, color, disabled = false, thumbnail }: { value: CaptionLayout; onChange: (value: CaptionLayout) => void; fontFamily: string; fontSize: number; color: string; disabled?: boolean; thumbnail?: string | null }) {
  const text = useLabels();
  const frame = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const move = (clientY: number) => { const rect = frame.current?.getBoundingClientRect(); if (rect?.height) onChange({ ...value, y: clampCaptionPosition((clientY - rect.top) / rect.height * 100) }); };
  const words = text.sample.split(" ").slice(0, value.wordsPerLine);
  return <div className="space-y-2">
    <div ref={frame} className="relative mx-auto aspect-[9/16] w-full max-w-[180px] overflow-hidden rounded-xl bg-[radial-gradient(circle_at_50%_30%,oklch(0.5_0.05_50),oklch(0.2_0.01_50))]" style={{ containerType: "inline-size", ...(thumbnail ? { backgroundImage: `linear-gradient(rgba(0,0,0,.3),rgba(0,0,0,.3)),url("${thumbnail}")`, backgroundPosition: "center", backgroundSize: "cover" } : {}) }} aria-label={text.preview}>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[10%] border-t border-dashed border-white/30 bg-black/10" aria-hidden="true" />
      <button type="button" disabled={disabled} aria-label={text.drag} title={text.drag} className="absolute inset-x-2 -translate-y-1/2 cursor-grab touch-none rounded-md px-1 py-1 text-center font-bold leading-snug outline-offset-4 focus-visible:outline-2 focus-visible:outline-white active:cursor-grabbing disabled:cursor-default" style={{ top: `${value.y * 100}%`, color, fontFamily: `'${fontFamily}', system-ui, sans-serif`, fontSize: captionPreviewFontSize(fontSize), textShadow: "0 2px 6px rgba(0,0,0,0.8), 0 0 2px rgba(0,0,0,0.9)", backgroundColor: value.background ? "rgba(0,0,0,.65)" : "transparent", textTransform: value.uppercase ? "uppercase" : "none" }} onPointerDown={(event) => { if (disabled) return; dragging.current = true; event.currentTarget.setPointerCapture(event.pointerId); move(event.clientY); }} onPointerMove={(event) => { if (dragging.current) move(event.clientY); }} onPointerUp={() => { dragging.current = false; }} onPointerCancel={() => { dragging.current = false; }} onKeyDown={(event) => { if (["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) { event.preventDefault(); const delta = event.shiftKey ? 5 : 1; const n = event.key === "Home" ? 10 : event.key === "End" ? 90 : value.y * 100 + (event.key === "ArrowUp" ? -delta : delta); onChange({ ...value, y: clampCaptionPosition(n) }); } }}>
        {words.map((word, index) => <span key={index} style={{ color: value.karaoke && index === Math.min(1, words.length - 1) ? value.accent : undefined }}>{index ? " " : ""}{word}</span>)}
      </button>
    </div>
    <p className="text-center text-[11px] text-muted-foreground">{text.drag}</p>
    <p className="text-center text-[10px] text-muted-foreground">{text.safe}</p>
  </div>;
}
