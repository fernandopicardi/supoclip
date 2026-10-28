"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

type Montage = {
  edit_id: string;
  title: string;
  revision: number;
  playback_seconds: number;
};

function duration(seconds: number) {
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function EditorialLibrary({ userId, query = "" }: { userId: string; query?: string }) {
  const [result, setResult] = useState<{ owner: string; edits: Montage[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      setError(false);
      try {
        const response = await fetch("/api/editorial/edits?limit=100", {
          cache: "no-store", signal: controller.signal,
        });
        if (!response.ok) throw new Error("Could not load montages");
        const data = await response.json();
        if (!controller.signal.aborted) setResult({ owner: userId, edits: data.edits });
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    const onFocus = () => { void load(); };
    window.addEventListener("focus", onFocus);
    return () => { controller.abort(); window.removeEventListener("focus", onFocus); };
  }, [userId, refresh]);

  const edits = result?.owner === userId ? result.edits : [];
  const search = query.trim().toLocaleLowerCase("pt-BR");
  const visible = edits.filter((edit) => !search || edit.title.toLocaleLowerCase("pt-BR").includes(search));

  return <section id="montagens" className="mt-8 space-y-4" aria-labelledby="montagens-heading" aria-busy={loading}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 id="montagens-heading" className="font-display text-lg font-bold tracking-tight">Montagens</h2>
        <p className="text-sm text-muted-foreground">Retome seus cortes, ajustes e versões exportadas.</p>
      </div>
      <Button variant="outline" size="sm" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>Atualizar montagens</Button>
    </div>
    {error && <p role="alert" className="text-sm text-destructive">Não foi possível carregar suas montagens. Use Atualizar montagens para tentar novamente.</p>}
    {loading && !result && <p role="status" className="text-sm text-muted-foreground">Carregando montagens…</p>}
    {!loading && !error && visible.length === 0 && <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
      {search ? "Nenhuma montagem corresponde à busca." : "Suas montagens aparecerão aqui quando você criar a primeira."}
    </p>}
    {visible.length > 0 && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {visible.map((edit) => <Link key={edit.edit_id} href={`/editorial/${edit.edit_id}`} className="space-y-2 rounded-xl border bg-background p-4 transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2">
        <h3 className="font-semibold break-words">{edit.title || "Montagem sem título"}</h3>
        <p className="text-sm text-muted-foreground">{duration(edit.playback_seconds)} · Revisão {edit.revision}</p>
        <p className="text-sm underline">Retomar montagem</p>
      </Link>)}
    </div>}
    {edits.length === 100 && <p className="text-xs text-muted-foreground">Mostrando as 100 montagens mais recentes.</p>}
  </section>;
}
