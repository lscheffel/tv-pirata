import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  ExternalLink,
  HardDrive,
  Magnet,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import { SourceDiagnosticInfo, SourceReleaseItem, UnifiedShow } from "../types";
import { api, isAbortError } from "../services/api";
import { useToast } from "../context/ToastContext";

interface TorrentModalProps {
  show: UnifiedShow | null;
  onClose: () => void;
}

function isSafeHttpUrl(url?: string | null): boolean {
  if (!url) return false;
  return url.startsWith("http://") || url.startsWith("https://");
}

function isSafeMagnetUrl(url?: string | null): boolean {
  if (!url) return false;
  return url.toLowerCase().startsWith("magnet:?xt=urn:");
}

export const TorrentModal: React.FC<TorrentModalProps> = ({ show, onClose }) => {
  const { showToast } = useToast();
  const [releases, setReleases] = useState<SourceReleaseItem[]>([]);
  const [approxMatches, setApproxMatches] = useState<SourceReleaseItem[]>([]);
  const [diagnostics, setDiagnostics] = useState<Record<string, SourceDiagnosticInfo>>({});
  const [availableSources, setAvailableSources] = useState<string[]>([]);
  const [activeSource, setActiveSource] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | number | null>(null);
  const [filterSeason, setFilterSeason] = useState<number | "ALL">("ALL");

  const [manualQuery, setManualQuery] = useState<string>("");
  const [appliedQueryOverride, setAppliedQueryOverride] = useState<string>("");

  const fetchReleases = useCallback(
    (
      liveMode: "auto" | "force",
      qOverride: string,
      targetSrc?: string,
      signal?: AbortSignal
    ) => {
      if (!show || !show.imdb_id) {
        setReleases([]);
        setApproxMatches([]);
        setDiagnostics({});
        setAvailableSources([]);
        return;
      }

      setLoading(true);
      const yr = show.first_air_date ? parseInt(String(show.first_air_date).slice(0, 4), 10) : undefined;

      api.sources
        .getReleases(show.imdb_id, targetSrc, {
          signal,
          live: liveMode,
          qOverride: qOverride || undefined,
          title: show.title,
          year: yr && !isNaN(yr) ? yr : undefined,
        })
        .then((data) => {
          setReleases(data.items);
          setApproxMatches(data.approx_matches || []);
          setDiagnostics(data.source_diagnostics || {});
          const srcKeys = Array.from(
            new Set([
              ...data.available_sources,
              ...Object.keys(data.source_diagnostics || {}),
            ])
          );
          setAvailableSources(srcKeys);
        })
        .catch(async (err) => {
          if (isAbortError(err)) return;
          try {
            const legacy = await api.torrents.getByImdb(show.imdb_id!);
            const mapped: SourceReleaseItem[] = legacy.map((r) => ({
              ...r,
              source_key: "eztv",
              source_name: "EZTV",
              release_type: "magnet",
              external_url: null,
            }));
            setReleases(mapped);
            setAvailableSources(mapped.length > 0 ? ["eztv"] : []);
          } catch {
            showToast("Erro ao buscar fontes de mídia disponíveis", "error");
            setReleases([]);
          }
        })
        .finally(() => {
          if (!signal || !signal.aborted) {
            setLoading(false);
          }
        });
    },
    [show, showToast]
  );

  useEffect(() => {
    if (!show) return;
    setActiveSource("all");
    setFilterSeason("ALL");
    setManualQuery(show.original_title || show.title || "");
    setAppliedQueryOverride("");
    const controller = new AbortController();
    fetchReleases("auto", "", undefined, controller.signal);
    return () => controller.abort();
  }, [show, fetchReleases]);

  const filteredBySource = useMemo(() => {
    if (activeSource === "all") return releases;
    return releases.filter((r) => r.source_key === activeSource);
  }, [releases, activeSource]);

  const filteredApprox = useMemo(() => {
    if (activeSource === "all") return approxMatches;
    return approxMatches.filter((r) => r.source_key === activeSource);
  }, [approxMatches, activeSource]);

  const activeChallenges = useMemo(() => {
    return Object.values(diagnostics).filter(
      (d) =>
        (activeSource === "all" || d.source_key === activeSource) &&
        (d.status === "challenge_required" ||
          (d.source_kind === "unique_web_source" && d.challenge_url && d.status !== "ok"))
    );
  }, [diagnostics, activeSource]);

  const seasons = useMemo(
    () =>
      Array.from(
        new Set(filteredBySource.map((r) => r.season).filter((s) => s > 0))
      ).sort((a, b) => a - b),
    [filteredBySource]
  );

  const displayedReleases = useMemo(
    () =>
      filterSeason === "ALL"
        ? filteredBySource
        : filteredBySource.filter((r) => r.season === filterSeason),
    [filteredBySource, filterSeason]
  );

  if (!show) return null;

  const formatBytes = (bytes: number) => {
    if (!bytes) return "N/A";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const handleCopyMagnet = (magnet: string, id: string | number) => {
    navigator.clipboard.writeText(magnet);
    setCopiedId(id);
    showToast("Link Magnet copiado para a área de transferência!", "success");
    setTimeout(() => setCopiedId(null), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl bg-surface-elevated border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-surface border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-300">
              <Magnet className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white line-clamp-1">
                Fontes de Mídia: {show.title}
              </h2>
              <p className="text-xs text-slate-300 font-mono">
                IMDB ID: {show.imdb_id || "Não informado"} • {releases.length} releases verificados
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() =>
                fetchReleases(
                  "force",
                  appliedQueryOverride,
                  activeSource === "all" ? undefined : activeSource
                )
              }
              className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold cursor-pointer transition-colors"
              title="Forçar busca ao vivo nos plugins externos"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span>Buscar Ao Vivo</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar modal de fontes de mídia"
              className="min-w-[44px] min-h-[44px] rounded-full flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Source Tabs, Query Refinement & Season Filters */}
        <div className="px-6 py-3 bg-surface/60 border-b border-white/5 space-y-2.5">
          {availableSources.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
              <button
                type="button"
                onClick={() => {
                  setActiveSource("all");
                  setFilterSeason("ALL");
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${activeSource === "all"
                  ? "bg-emerald-500 text-slate-950"
                  : "bg-white/5 text-slate-300 hover:bg-white/10"
                  }`}
              >
                Todas as Fontes ({releases.length})
              </button>
              {availableSources.map((srcKey) => {
                const count = releases.filter((r) => r.source_key === srcKey).length;
                const diag = diagnostics[srcKey];
                const hasChallenge = diag?.status === "challenge_required";
                return (
                  <button
                    type="button"
                    key={srcKey}
                    onClick={() => {
                      setActiveSource(srcKey);
                      setFilterSeason("ALL");
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase whitespace-nowrap transition-colors flex items-center gap-1.5 cursor-pointer ${activeSource === srcKey
                      ? "bg-emerald-500 text-slate-950"
                      : hasChallenge
                        ? "bg-amber-500/20 text-amber-200 border border-amber-400/50"
                        : "bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                  >
                    {hasChallenge && <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                    <span>
                      {diag?.source_name || srcKey} ({count})
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Manual Query Refinement Bar (DEC-003) */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const q = manualQuery.trim();
              setAppliedQueryOverride(q);
              fetchReleases("force", q, activeSource === "all" ? undefined : activeSource);
            }}
            className="flex items-center gap-2"
          >
            <div className="relative flex-1">
              <label htmlFor="modal-refine-query" className="sr-only">
                Refinar termo de busca nas fontes
              </label>
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="modal-refine-query"
                type="text"
                value={manualQuery}
                onChange={(e) => setManualQuery(e.target.value)}
                placeholder="Refinar termo de busca nas fontes externas..."
                className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-xl pl-8 pr-3 text-xs text-white placeholder-slate-400"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="min-h-[38px] px-3.5 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-bold text-slate-100 cursor-pointer"
            >
              Refinar Busca
            </button>
          </form>

          {seasons.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
              <button
                type="button"
                onClick={() => setFilterSeason("ALL")}
                className={`px-3 py-1 rounded-full text-xs font-bold transition-colors cursor-pointer ${filterSeason === "ALL"
                  ? "bg-brand-red text-white"
                  : "bg-white/5 text-slate-300 hover:bg-white/10"
                  }`}
              >
                Todas Temporadas
              </button>
              {seasons.map((s) => (
                <button
                  type="button"
                  key={s}
                  onClick={() => setFilterSeason(s)}
                  className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${filterSeason === s
                    ? "bg-brand-red text-white"
                    : "bg-white/5 text-slate-300 hover:bg-white/10"
                    }`}
                >
                  Temp. {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* CAPTCHA / Anti-Bot Manual Handoff Banner (DEC-004) */}
          {activeChallenges.map((diag) => (
            <div
              key={`challenge-${diag.source_key}`}
              role="alert"
              className="p-4 rounded-xl bg-amber-950/60 border border-amber-400/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-bold text-amber-200">
                    Desafio Anti-Bot / CAPTCHA detectado em {diag.source_name}
                  </h4>
                  <p className="text-xs text-slate-200 mt-0.5">
                    {diag.message ||
                      "Esta fonte única exige verificação humana no navegador antes de liberar os links."}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {isSafeHttpUrl(diag.challenge_url) && (
                  <a
                    href={diag.challenge_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="min-h-[44px] px-4 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-extrabold flex items-center gap-1.5 shadow-lg transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Abrir Página no Navegador
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => fetchReleases("force", appliedQueryOverride, diag.source_key)}
                  className="min-h-[44px] px-3.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-bold cursor-pointer"
                >
                  Tentar Novamente
                </button>
              </div>
            </div>
          ))}

          {!show.imdb_id ? (
            <div className="text-center py-12 text-slate-300">
              Esta obra não possui IMDb ID mapeado para consulta nas Fontes de Dados.
            </div>
          ) : loading && displayedReleases.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <div className="w-8 h-8 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-300">
                Consultando cache local e plugins externos em paralelo...
              </p>
            </div>
          ) : displayedReleases.length === 0 && filteredApprox.length === 0 ? (
            <div className="text-center py-12 text-slate-300">
              Nenhuma fonte ou magnet encontrado para este filtro. Use &quot;Buscar Ao Vivo&quot; ou refine o termo acima.
            </div>
          ) : (
            <>
              {displayedReleases.map((r) => (
                <div
                  key={`${r.source_key}-${r.id}`}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-surface border border-white/10 hover:border-white/25 transition-colors"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[11px] font-black uppercase border border-emerald-500/30">
                        {r.source_name || r.source_key}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-white/10 text-xs font-bold text-slate-100">
                        {r.quality || "Unknown"}
                      </span>
                      {r.season > 0 && (
                        <span className="px-2 py-0.5 rounded bg-brand-red/20 text-brand-red text-xs font-bold">
                          S{String(r.season).padStart(2, "0")}E{String(r.episode).padStart(2, "0")}
                        </span>
                      )}
                      <h4 className="text-sm font-semibold text-white break-all">{r.title}</h4>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-300">
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                        {formatBytes(r.size_bytes)}
                      </span>
                      <span className="text-emerald-300 font-semibold">▲ {r.seeds} Seeds</span>
                      <span className="text-sky-300 font-medium">▼ {r.peers} Peers</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {isSafeMagnetUrl(r.magnet_url) && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleCopyMagnet(r.magnet_url, r.id)}
                          className="flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-lg bg-white/10 hover:bg-white/15 text-slate-100 text-xs font-semibold transition-colors cursor-pointer"
                        >
                          {copiedId === r.id ? (
                            <Check className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                          {copiedId === r.id ? "Copiado" : "Copiar Magnet"}
                        </button>

                        <a
                          href={r.magnet_url}
                          className="flex items-center gap-1.5 min-h-[44px] px-4 rounded-lg bg-brand-red hover:bg-brand-redHover text-white text-xs font-bold shadow-lg transition-all"
                        >
                          <ExternalLink className="w-4 h-4" />
                          Abrir Cliente
                        </a>
                      </>
                    )}
                    {isSafeHttpUrl(r.external_url) && (
                      <a
                        href={r.external_url!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-xs font-bold transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                        Ver Link
                      </a>
                    )}
                    {!isSafeMagnetUrl(r.magnet_url) && isSafeHttpUrl(r.torrent_url) && (
                      <a
                        href={r.torrent_url!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        Torrent
                      </a>
                    )}
                  </div>
                </div>
              ))}

              {/* Ephemeral Approximate Matches (0.60 - 0.84 confidence, not persisted to MediaBadge) */}
              {filteredApprox.length > 0 && (
                <div className="pt-4 border-t border-white/10 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-amber-300">
                      Correspondência aproximada (não salva no cartaz • {filteredApprox.length})
                    </span>
                    <span className="text-[11px] text-slate-300">
                      Confiança entre 60% e 84% — verifique título/ano antes de abrir
                    </span>
                  </div>
                  {filteredApprox.map((r) => (
                    <div
                      key={`approx-${r.source_key}-${r.id}`}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 rounded-xl bg-surface/60 border border-amber-400/30"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-[10px] font-black uppercase">
                            {r.source_name} • Correspondência aproximada (não salva)
                          </span>
                          <h4 className="text-xs font-semibold text-white break-all">{r.title}</h4>
                        </div>
                        <div className="text-[11px] text-slate-300">
                          ▲ {r.seeds} Seeds • Confiança:{" "}
                          {Math.round((r.match_confidence ?? 0.7) * 100)}%
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {isSafeMagnetUrl(r.magnet_url) && (
                          <a
                            href={r.magnet_url}
                            className="min-h-[44px] px-3.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-bold flex items-center gap-1.5"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            Magnet
                          </a>
                        )}
                        {isSafeHttpUrl(r.external_url) && (
                          <a
                            href={r.external_url!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="min-h-[44px] px-3.5 rounded-lg bg-cyan-500/20 text-cyan-200 text-xs font-bold flex items-center gap-1.5"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            Abrir Link
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
