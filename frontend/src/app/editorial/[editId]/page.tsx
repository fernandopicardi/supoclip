"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Cut = { id: string; start: number; end: number };
type Clip = { id: string; start: number; end: number; cuts: Cut[] };
type Export = { job_id: string; status: string; revision: number; progress?: number };
type Edit = {
  edit_id: string;
  revision: number;
  document: { title: string; clips: Clip[] };
  timeline: { playback_seconds: number };
  exports: Export[];
};

export default function EditorialPage({ params }: { params: Promise<{ editId: string }> }) {
  const { editId } = use(params);
  const base = `/api/editorial/edits/${encodeURIComponent(editId)}`;
  const [edit, setEdit] = useState<Edit | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);

  const request = useCallback(async (url: string, body?: unknown) => {
    const response = await fetch(url, body === undefined ? { cache: "no-store" } : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(response.status === 409
      ? "A montagem mudou. Atualize antes de continuar. Seus ajustes não foram sobrescritos."
      : String(data.detail || data.error || "Não foi possível concluir a operação."));
    return data;
  }, []);

  const refresh = useCallback(async () => {
    try { setEdit(await request(base)); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Falha ao abrir montagem."); }
  }, [base, request]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function apply(operations: unknown[]) {
    if (!edit || busy) return;
    setBusy(true);
    try {
      await request(`${base}/checkpoints`, { revision: edit.revision, request_id: crypto.randomUUID() });
      await request(`${base}/operations`, { revision: edit.revision, request_id: crypto.randomUUID(), operations });
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Falha ao salvar."); }
    finally { setBusy(false); }
  }

  async function exportVideo() {
    if (!edit || busy) return;
    setBusy(true);
    try {
      await request(`${base}/exports`, { revision: edit.revision, request_id: crypto.randomUUID() });
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Falha ao exportar."); }
    finally { setBusy(false); }
  }

  const completed = edit?.exports.filter((job) => job.status === "completed") ?? [];
  const preview = completed.find((job) => job.job_id === selectedJob) ?? completed[0];
  const button = "rounded border px-3 py-2 text-sm disabled:opacity-40";

  return <main className="mx-auto max-w-5xl space-y-5 p-6">
    <Link href="/list" className="text-sm underline">Voltar aos projetos</Link>
    <h1 className="text-2xl font-semibold">{edit?.document.title || "Montagem dirigida"}</h1>
    {error && <p role="alert" className="rounded border border-red-500 p-3">{error}</p>}
    <div className="flex flex-wrap items-center gap-3">
      <button className={button} onClick={() => void refresh()} disabled={busy}>Atualizar montagem</button>
      <button className={button} onClick={() => void exportVideo()} disabled={busy || !edit?.document.clips.length}>Exportar versão atual</button>
      {edit && <span>{edit.document.clips.length} trechos · {edit.timeline.playback_seconds.toFixed(2)} segundos</span>}
    </div>
    {preview && <section className="space-y-2">
      {preview.revision !== edit?.revision && <p>A prévia mostra uma versão anterior. Exporte a montagem atual para conferir os novos ajustes.</p>}
      <video key={preview.job_id} controls preload="metadata" className="mx-auto max-h-[70vh] max-w-full" src={`${base}/exports/${preview.job_id}/file`} />
      <a className="underline" href={`${base}/exports/${preview.job_id}/file`} download>Baixar vídeo</a>
    </section>}
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Trechos na ordem de reprodução</h2>
      <p className="text-sm">Início, fim e cortes usam segundos do vídeo original. Revise as emendas pelo áudio. Cada salvamento preserva uma cópia da montagem anterior.</p>
      {edit?.document.clips.map((clip, index) => <form key={`${clip.id}-${edit.revision}`} className="space-y-3 rounded border p-4" onSubmit={(event) => {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        void apply([{ op: "set_clip_range", clip_id: clip.id, start: Number(data.get("start")), end: Number(data.get("end")) }]);
      }}>
        <div className="flex flex-wrap items-end gap-3">
          <strong>Trecho {index + 1}</strong>
          <label>Início <input className="ml-2 w-28 rounded border bg-transparent p-1" name="start" type="number" step="0.001" min="0" required defaultValue={clip.start} /></label>
          <label>Fim <input className="ml-2 w-28 rounded border bg-transparent p-1" name="end" type="number" step="0.001" min="0" required defaultValue={clip.end} /></label>
          <button className={button} disabled={busy}>Salvar limites</button>
          <button type="button" className={button} disabled={busy || index === 0} onClick={() => void apply([{ op: "move_clip", clip_id: clip.id, index: index - 1 }])}>Mover para cima</button>
          <button type="button" className={button} disabled={busy || index === edit.document.clips.length - 1} onClick={() => void apply([{ op: "move_clip", clip_id: clip.id, index: index + 1 }])}>Mover para baixo</button>
        </div>
        {clip.cuts.map((cut) => <div key={cut.id} className="flex items-center gap-3 text-sm">
          <span>Corte interno: {cut.start.toFixed(3)}–{cut.end.toFixed(3)}s</span>
          <button className={button} type="button" disabled={busy} onClick={() => void apply([{ op: "remove_cut", clip_id: clip.id, cut_id: cut.id }])}>Recuperar esta fala</button>
        </div>)}
      </form>)}
    </section>
    {!!edit?.exports.length && <section className="space-y-2">
      <h2 className="text-lg font-semibold">Exportações</h2>
      {edit.exports.map((job) => <div key={job.job_id} className="flex items-center gap-3 text-sm">
        <span>Versão {job.revision}: {job.status} {job.progress !== undefined ? `${job.progress}%` : ""}</span>
        {job.status === "completed" && <button className={button} onClick={() => setSelectedJob(job.job_id)}>Ver esta versão</button>}
      </div>)}
      <p className="text-sm">Use Atualizar montagem para consultar o progresso.</p>
    </section>}
  </main>;
}
