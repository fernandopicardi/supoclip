"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { drawEditorFrame, loadEditorFont } from "@/lib/editor/render";
import { timecode } from "@/lib/editor/document";
import { captionDocument, foregroundGeometry, Montage, montageDuration, montageRanges, playbackTarget, PreviewData } from "@/lib/editorial-preview";

export function EditorialPreview({ document: doc, data, seekClip }: { document: Montage; data: PreviewData; seekClip: { id: string; tick: number } | null }) {
  const video = useRef<HTMLVideoElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const rangeIndex = useRef(0), currentTime = useRef(0);
  const [playing, setPlaying] = useState(false), [time, setTime] = useState(0), [error, setError] = useState("");
  const [fontReady, setFontReady] = useState(false), [mediaReady, setMediaReady] = useState(false);
  const clips = doc.clips;
  const ranges = useMemo(() => montageRanges({ clips }), [clips]);
  const duration = montageDuration(ranges);
  const captions = useMemo(() => captionDocument(doc, data.words, ranges), [doc, data.words, ranges]);
  const size = doc.framing.aspect === "vertical" ? [720, 1280] : doc.framing.aspect === "square" ? [720, 720] : [1280, 720];

  useEffect(() => {
    let alive = true;
    setFontReady(false);
    void loadEditorFont(doc.captions.font).then(() => { if (alive) setFontReady(true); }).catch(() => {
      if (alive) setError("Não foi possível carregar a fonte da legenda. Confira a conexão antes de exportar.");
    });
    return () => { alive = false; };
  }, [doc.captions.font]);

  const paint = useCallback(() => {
    const v = video.current, ctx = canvas.current?.getContext("2d"), r = ranges[rangeIndex.current];
    if (!v || !ctx || v.readyState < 2 || !r || !fontReady) return;
    const { width, height } = ctx.canvas;
    const g = foregroundGeometry(r.clip.framing ?? doc.framing, data.source.width, data.source.height, width, height);
    drawEditorFrame(ctx, captions, data.source.width, data.source.height, currentTime.current, () => {
      if (doc.background === "blur") {
        ctx.save();
        const scale = Math.max(width / g.width, height / g.height);
        const w = g.width * scale, h = g.height * scale;
        ctx.filter = "blur(24px) saturate(80%)";
        // Extend blurred edges beyond the canvas; captions are drawn afterwards.
        ctx.drawImage(v, g.sx, g.sy, g.sw, g.sh, (width - w) / 2 - 24, (height - h) / 2 - 24, w + 48, h + 48);
        ctx.filter = "none"; ctx.fillStyle = "rgba(0,0,0,.08)"; ctx.fillRect(0, 0, width, height);
        ctx.restore();
      }
      ctx.drawImage(v, g.sx, g.sy, g.sw, g.sh, g.x, g.y, g.width, g.height);
    }, data.captionLooks);
  }, [captions, data, doc.background, doc.framing, fontReady, ranges]);

  const seek = useCallback((position: number) => {
    const target = playbackTarget(ranges, position);
    if (!target || !video.current) return;
    rangeIndex.current = target.index;
    currentTime.current = position;
    setTime(position);
    video.current.currentTime = target.source;
  }, [ranges]);

  useEffect(() => { paint(); }, [paint]);
  useEffect(() => { video.current?.pause(); seek(0); }, [seek]);
  useEffect(() => {
    if (!seekClip) return;
    const r = ranges.find(r => r.clip.id === seekClip.id);
    if (r) { video.current?.pause(); seek(r.playback); }
  }, [seekClip, ranges, seek]);

  useEffect(() => {
    let frame = 0, lastPaint = -1, lastUi = -1;
    const update = () => {
      const v = video.current, r = ranges[rangeIndex.current];
      if (v && r && !v.seeking && !v.paused) {
        if (!v.paused && v.currentTime >= r.end) {
          if (rangeIndex.current + 1 < ranges.length) {
            const next = ranges[++rangeIndex.current];
            v.currentTime = next.start;
            currentTime.current = next.playback;
          } else { v.pause(); currentTime.current = duration; }
        } else {
          currentTime.current = r.playback + Math.max(0, Math.min(r.end - r.start, v.currentTime - r.start));
        }
        if (Math.abs(currentTime.current - lastUi) >= .05 || v.paused) { setTime(currentTime.current); lastUi = currentTime.current; }
        if (Math.abs(v.currentTime - lastPaint) >= 1 / 30 || v.paused) { paint(); lastPaint = v.currentTime; }
      }
      frame = requestAnimationFrame(update);
    };
    frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [duration, paint, ranges]);

  async function toggle() {
    const v = video.current;
    if (!v) return;
    if (!v.paused) { v.pause(); return; }
    if (currentTime.current >= duration - .01) seek(0);
    try { await v.play(); setError(""); } catch { setError("Não foi possível reproduzir o original. Tente novamente."); }
  }

  return <section className="space-y-3 rounded-xl border p-4" aria-label="Prévia da montagem">
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Prévia antes de exportar</h2><span className="text-xs">{doc.framing.aspect === "vertical" ? "9:16" : doc.framing.aspect === "square" ? "1:1" : "16:9"}</span></div>
    <video ref={video} src={`/api/editorial/sources/${encodeURIComponent(doc.source_id)}/media`} preload="auto" playsInline className="hidden" aria-hidden="true"
      onLoadedMetadata={() => { setMediaReady(true); seek(0); }} onLoadedData={paint} onSeeked={paint}
      onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
      onError={() => setError("Não foi possível abrir o vídeo original desta montagem.")} />
    <canvas ref={canvas} width={size[0]} height={size[1]} aria-label="Vídeo original com legendas e enquadramento" className="mx-auto block max-h-[65vh] max-w-full rounded-lg bg-black" style={{ aspectRatio: `${size[0]}/${size[1]}` }} />
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    <div className="flex items-center gap-3">
      <button type="button" className="rounded border px-3 py-2 disabled:opacity-40" disabled={!fontReady || !mediaReady || !duration} onClick={() => void toggle()}>{playing ? "Pausar" : "Reproduzir"}</button>
      <output className="text-sm tabular-nums">{timecode(time)} / {timecode(duration)}</output>
    </div>
    <input aria-label="Posição na montagem" type="range" className="w-full" min="0" max={duration || 1} step="0.01" value={time} disabled={!mediaReady || !duration} onChange={event => { video.current?.pause(); seek(Number(event.target.value)); }} />
    <p className="text-xs text-muted-foreground">A prévia reproduz o original com os ajustes locais. Confira a fala e as emendas. O desfoque e a suavização das letras podem variar ligeiramente na exportação.</p>
  </section>;
}
