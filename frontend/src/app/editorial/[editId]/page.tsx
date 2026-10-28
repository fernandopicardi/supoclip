"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { EditorialPreview } from "@/components/editorial-preview";
import { MontageControls, type MontageFont } from "@/components/montage-controls";
import { timecode } from "@/lib/editor/document";
import { Montage, montageDuration, montageError, montageRanges, PreviewData } from "@/lib/editorial-preview";

type Export = { job_id: string; status: string; revision: number; progress?: number };
type Edit = { edit_id: string; revision: number; document: Montage; exports: Export[] };
const button = "rounded-lg border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-40";

export default function EditorialPage({ params }: { params: Promise<{ editId: string }> }) {
  const { editId } = use(params);
  const base = `/api/editorial/edits/${encodeURIComponent(editId)}`;
  const [edit, setEdit] = useState<Edit | null>(null), [draft, setDraft] = useState<Montage | null>(null);
  const [data, setData] = useState<PreviewData | null>(null), [fonts, setFonts] = useState<MontageFont[]>([]);
  const [error, setError] = useState(""), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [seekClip, setSeekClip] = useState<{ id: string; tick: number } | null>(null);
  const pending = useRef<{ document: string; revision: number; request_id: string } | null>(null);
  const pendingExport = useRef<{ revision: number; request_id: string } | null>(null);
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(edit?.document);
  const validation = draft && data ? montageError(draft, data.source.duration) : "";

  const request = useCallback(async (url: string, body?: unknown) => {
    const response = await fetch(url, body === undefined ? { cache: "no-store" } : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(response.status === 409
      ? "A montagem mudou em outra sessão. Seus ajustes continuam nesta tela. Atualize somente quando decidir descartá-los."
      : typeof result.detail === "string" ? result.detail : "Não foi possível concluir a operação. Confira os valores e tente novamente.");
    return result;
  }, []);

  useEffect(() => {
    let alive = true;
    setEdit(null); setDraft(null); setData(null);
    void Promise.all([request(base), request(`${base}/preview-data`), request("/api/fonts")]).then(([loaded, preview, fontData]) => {
      if (alive) { setEdit(loaded); setDraft(structuredClone(loaded.document)); setData(preview); setFonts(fontData.fonts); setError(""); }
    }).catch(cause => { if (alive) setError(cause instanceof Error ? cause.message : "Falha ao abrir montagem."); });
    return () => { alive = false; };
  }, [base, request]);

  useEffect(() => {
    if (!dirty) return;
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);

  async function refresh() {
    if (dirty && !window.confirm("Descartar os ajustes que ainda não foram salvos e carregar a versão do servidor?")) return;
    setBusy(true);
    try { const loaded = await request(base); setEdit(loaded); setDraft(structuredClone(loaded.document)); pending.current = null; setError(""); setNotice("Montagem atualizada."); }
    catch (cause) { setError(String(cause instanceof Error ? cause.message : cause)); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!edit || !draft || busy || validation || !dirty) return;
    setBusy(true); setError("");
    const serialized = JSON.stringify(draft);
    if (!pending.current || pending.current.document !== serialized || pending.current.revision !== edit.revision)
      pending.current = { document: serialized, revision: edit.revision, request_id: crypto.randomUUID() };
    try {
      const result = await request(`${base}/draft`, { revision: edit.revision, request_id: pending.current.request_id, document: draft });
      setEdit({ ...edit, ...result }); setDraft(structuredClone(result.document)); pending.current = null;
      setNotice("Montagem salva. A versão anterior foi preservada. Você já pode exportar.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Falha ao salvar. Seus ajustes continuam nesta tela."); }
    finally { setBusy(false); }
  }
  async function exportVideo() {
    if (!edit || busy || dirty || validation || !draft?.clips.length) return;
    setBusy(true); setError("");
    if (pendingExport.current?.revision !== edit.revision) pendingExport.current = { revision: edit.revision, request_id: crypto.randomUUID() };
    try {
      await request(`${base}/exports`, pendingExport.current);
      const loaded = await request(base); setEdit(loaded); pendingExport.current = null;
      setNotice("Exportação solicitada. Use Atualizar montagem para consultar o progresso.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Falha ao exportar."); }
    finally { setBusy(false); }
  }
  const job = edit?.exports.find(j => j.job_id === selectedJob && j.status === "completed");
  const duration = draft ? montageDuration(montageRanges(draft)) : 0;
  const activeExport = edit?.exports.some(j => ["queued", "rendering", "processing"].includes(j.status));

  return <main className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
    <Link href="/list" className="text-sm underline" onClick={event => { if (dirty && !window.confirm("Sair e descartar os ajustes ainda não salvos?")) event.preventDefault(); }}>Voltar aos projetos</Link>
    <h1 className="text-2xl font-semibold">{draft?.title || "Montagem dirigida"}</h1>
    <p className="text-sm text-muted-foreground">Revise a prévia, ajuste e salve a montagem. Exporte quando estiver satisfeito com o resultado.</p>
    {error && <p role="alert" className="rounded border border-red-500 p-3">{error}</p>}
    {notice && <p role="status" className="rounded border p-3">{notice}</p>}
    <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 rounded-xl border bg-background p-3 shadow-sm">
      <button className={button} onClick={() => void refresh()} disabled={busy || !edit}>Atualizar montagem</button>
      <button className={`${button} bg-primary text-primary-foreground`} onClick={() => void save()} disabled={busy || !dirty || !!validation}>Salvar montagem</button>
      <button className={button} onClick={() => void exportVideo()} disabled={busy || dirty || !!validation || !draft?.clips.length || activeExport}>Exportar versão salva</button>
      <span role="status" className="text-sm">{dirty ? "Ajustes não salvos" : "Montagem salva"} · {timecode(duration)}</span>
      {dirty && <span className="text-xs">Salve para liberar a exportação.</span>}
    </div>
    {draft && data && <div className="grid items-start gap-6 lg:grid-cols-[minmax(280px,420px)_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-24"><EditorialPreview document={draft} data={data} seekClip={seekClip} /></div>
      <MontageControls document={draft} data={data} fonts={fonts} disabled={busy} validation={validation}
        onChange={value => { setDraft(value); setNotice(""); }} onSeek={id => setSeekClip({ id, tick: Date.now() })} />
    </div>}
    {!!edit?.exports.length && <section className="space-y-3 rounded-xl border p-4">
      <h2 className="text-lg font-semibold">Exportações anteriores</h2>
      <p className="text-sm text-muted-foreground">Cada arquivo corresponde à revisão indicada. A prévia acima mostra os ajustes atuais.</p>
      {edit.exports.map(j => <div key={j.job_id} className="flex flex-wrap items-center gap-3 text-sm"><span>Revisão {j.revision}: {j.status} {j.progress !== undefined ? `${j.progress}%` : ""}</span>{j.status === "completed" && <button className={button} onClick={() => setSelectedJob(j.job_id)}>Abrir exportação da revisão {j.revision}</button>}</div>)}
      {job && <div className="space-y-2"><video controls preload="metadata" className="max-h-[60vh] max-w-full" src={`${base}/exports/${job.job_id}/file`} /><a className="underline" href={`${base}/exports/${job.job_id}/file`} download>Baixar esta exportação</a></div>}
    </section>}
  </main>;
}
