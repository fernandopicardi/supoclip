"use client";

import { CaptionLayoutControls } from "@/components/caption-layout-controls";
import { DEFAULT_CAPTION_LAYOUT } from "@/lib/caption-layout";
import { CaptionStyle, Framing } from "@/lib/editor/document";
import { Clip, Montage, PreviewData } from "@/lib/editorial-preview";

export type MontageFont = { name: string; display_name?: string };
const button = "rounded-lg border px-3 py-2 text-sm disabled:opacity-40";
const input = "min-w-0 rounded border bg-background p-2";

export function MontageControls({ document: doc, data, fonts, disabled, validation, onChange, onSeek }: {
  document: Montage; data: PreviewData; fonts: MontageFont[]; disabled: boolean; validation: string;
  onChange: (value: Montage) => void; onSeek: (id: string) => void;
}) {
  const update = (patch: Partial<Montage>) => onChange({ ...doc, ...patch });
  const caption = (patch: Partial<CaptionStyle>) => update({ captions: { ...doc.captions, ...patch } });
  const clipPatch = (id: string, patch: Partial<Clip>) => update({ clips: doc.clips.map(c => c.id === id ? { ...c, ...patch } : c) });
  function move(index: number, delta: number) {
    const clips = [...doc.clips]; [clips[index], clips[index + delta]] = [clips[index + delta], clips[index]]; update({ clips });
  }
  return <fieldset disabled={disabled} className="min-w-0 space-y-5 disabled:opacity-60">
    <legend className="sr-only">Ajustes da montagem</legend>
    <section className="space-y-4 rounded-xl border p-4">
      <h2 className="text-lg font-semibold">Imagem e legendas</h2>
      <label className="flex flex-wrap items-center justify-between gap-2">Fundo do vídeo
        <select className={input} value={doc.background} onChange={event => update({ background: event.target.value as Montage["background"] })}><option value="black">Preto</option><option value="blur">Vídeo desfocado</option></select>
      </label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={doc.captions.enabled} onChange={event => caption({ enabled: event.target.checked })} />Exibir legendas</label>
      <label className="flex flex-wrap items-center justify-between gap-2">Fonte da legenda
        <select className={`${input} max-w-full`} value={doc.captions.font} onChange={event => caption({ font: event.target.value })}>
          {!fonts.some(f => f.name === doc.captions.font) && <option value={doc.captions.font}>{doc.captions.font}</option>}
          {fonts.map(f => <option key={f.name} value={f.name}>{f.display_name || f.name}</option>)}
        </select>
      </label>
      <label className="flex items-center justify-between gap-2">Tamanho da legenda <input className={`${input} w-24`} type="number" min="20" max="512" value={doc.captions.size} onChange={event => { const size = Number(event.target.value); if (Number.isInteger(size) && size >= 20 && size <= 512) caption({ size }); }} /></label>
      <p className="text-xs text-muted-foreground">Ajuste pelo vídeo à esquerda. A escala tipográfica é compartilhada com a exportação.</p>
      <label className="flex items-center justify-between gap-2">Cor da legenda <input type="color" value={doc.captions.color} onChange={event => caption({ color: event.target.value })} /></label>
      <CaptionLayoutControls value={{ ...DEFAULT_CAPTION_LAYOUT, ...doc.captions }} disabled={disabled} onChange={value => caption(value)} />
    </section>
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Trechos na ordem de reprodução</h2>
      <p className="text-sm text-muted-foreground">Início, fim e cortes internos usam segundos do vídeo original. Altere a ordem e confira as emendas na prévia. Os ajustes só são gravados ao salvar.</p>
      {validation && <p role="alert" className="text-sm text-red-600">{validation}</p>}
      {doc.clips.map((clip, index) => <article key={clip.id} className="space-y-4 rounded-xl border p-4" aria-label={`Trecho ${index + 1}`}>
        <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto font-semibold">Trecho {index + 1}</h3>
          <button className={button} type="button" onClick={() => onSeek(clip.id)}>Ouvir trecho {index + 1}</button>
          <button className={button} type="button" disabled={index === 0} onClick={() => move(index, -1)}>Subir trecho {index + 1}</button>
          <button className={button} type="button" disabled={index === doc.clips.length - 1} onClick={() => move(index, 1)}>Descer trecho {index + 1}</button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(["start", "end"] as const).map(key => <label key={key} className="grid gap-1 text-sm">{key === "start" ? "Início" : "Fim"} do trecho {index + 1} (s)<input className={`${input} w-full`} type="number" step="0.01" min="0" max={data.source.duration} value={clip[key]} onChange={event => clipPatch(clip.id, { [key]: Number(event.target.value) })} /></label>)}
        </div>
        <details className="space-y-3"><summary className="cursor-pointer text-sm">Enquadramento do trecho {index + 1}</summary>
          <label className="flex flex-wrap justify-between gap-2">Ajuste da imagem <select className={input} value={(clip.framing ?? doc.framing).fit} onChange={event => clipPatch(clip.id, { framing: { ...(clip.framing ?? doc.framing), fit: event.target.value as Framing["fit"] } })}><option value="contain">Preservar imagem</option><option value="cover">Preencher tela</option></select></label>
          {(["zoom", "x", "y"] as const).map(key => <label key={key} className="grid gap-1 text-sm">{key === "zoom" ? "Zoom" : key === "x" ? "Posição horizontal" : "Posição vertical"}<input type="range" min={key === "zoom" ? 1 : 0} max={key === "zoom" ? 3 : 1} step="0.01" value={(clip.framing ?? doc.framing)[key]} onChange={event => clipPatch(clip.id, { framing: { ...(clip.framing ?? doc.framing), [key]: Number(event.target.value) } })} /></label>)}
        </details>
        <details className="space-y-3"><summary className="cursor-pointer text-sm">Cortes internos ({clip.cuts.length})</summary>
          {clip.cuts.map((cut, n) => <div key={cut.id} className="grid gap-2 rounded border p-2 sm:grid-cols-[1fr_1fr_auto]">
            {(["start", "end"] as const).map(key => <label key={key} className="grid gap-1 text-sm">{key === "start" ? "Início" : "Fim"} do corte {n + 1}<input className={`${input} w-full`} type="number" step="0.01" value={cut[key]} onChange={event => clipPatch(clip.id, { cuts: clip.cuts.map(c => c.id === cut.id ? { ...c, [key]: Number(event.target.value) } : c) })} /></label>)}
            <button type="button" className={button} onClick={() => clipPatch(clip.id, { cuts: clip.cuts.filter(c => c.id !== cut.id) })}>Recuperar fala</button>
          </div>)}
          <button type="button" className={button} onClick={() => clipPatch(clip.id, { cuts: [...clip.cuts, { id: crypto.randomUUID(), start: clip.start, end: Math.min(clip.end, clip.start + .5) }] })}>Adicionar corte interno</button>
        </details>
        <details className="space-y-2"><summary className="cursor-pointer text-sm">Corrigir texto da legenda</summary>
          <p className="text-xs text-muted-foreground">As correções mudam somente o texto desta ocorrência. Para retirar uma fala, use os cortes internos.</p>
          <div className="flex max-h-64 flex-wrap gap-2 overflow-y-auto p-1">{data.words.filter(w => w.start >= clip.start && w.end <= clip.end).map(w => <label key={w.id} className="grid gap-1 text-xs"><span>{w.start.toFixed(2)}s</span><input aria-label={`Legenda em ${w.start.toFixed(2)}s do trecho ${index + 1}`} className={`${input} w-32 text-sm`} maxLength={200} value={doc.word_text[`${clip.id}:${w.id}`] ?? w.text} onChange={event => update({ word_text: { ...doc.word_text, [`${clip.id}:${w.id}`]: event.target.value } })} /></label>)}</div>
        </details>
      </article>)}
    </section>
  </fieldset>;
}
