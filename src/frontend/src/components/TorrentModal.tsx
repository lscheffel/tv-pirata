import React, { useEffect, useMemo, useState } from "react";
import { X, Magnet, Copy, Check, HardDrive, ExternalLink, Download } from "lucide-react";
import { SourceReleaseItem, UnifiedShow } from "../types";
import { api, isAbortError } from "../services/api";
import { useToast } from "../context/ToastContext";

interface TorrentModalProps {
  show: UnifiedShow | null;
  onClose: () => void;
}

export const TorrentModal: React.FC<TorrentModalProps> = ({ show, onClose }) => {
  const { showToast } = useToast();
  const [releases, setReleases] = useState<SourceReleaseItem[]>([]);
  const [availableSources, setAvailableSources] = useState<string[]>([]);
  const [activeSource, setActiveSource] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | number | null>(null);
  const [filterSeason, setFilterSeason] = useState<number | "ALL">("ALL");

  useEffect(() => {
    if (!show || !show.imdb_id) {
      setReleases([]);
      setAvailableSources([]);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setActiveSource("all");
    setFilterSeason("ALL");

    api.sources
      .getReleases(show.imdb_id, undefined, { signal: controller.signal })
      .then((data) => {
        setReleases(data.items);
        setAvailableSources(data.available_sources);
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
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [show, showToast]);

  const filteredBySource = useMemo(() => {
    if (activeSource === "all") return releases;
    return releases.filter((r) => r.source_key === activeSource);
  }, [releases, activeSource]);

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
      <div className="relative w-full max-w-4xl bg-surface-elevated border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
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
                IMDB ID: {show.imdb_id || "Não informado"} • {releases.length} fontes/releases
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar modal de fontes de mídia"
            className="min-w-[44px] min-h-[44px] rounded-full flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source & Season Filters */}
        {(availableSources.length > 0 || seasons.length > 0) && (
          <div className="px-6 py-3 bg-surface/60 border-b border-white/5 space-y-2">
            {availableSources.length > 0 && (
              <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
                <button
                  type="button"
                  onClick={() => {
                    setActiveSource("all");
                    setFilterSeason("ALL");
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${
                    activeSource === "all"
                      ? "bg-emerald-500 text-slate-950"
                      : "bg-white/5 text-slate-300 hover:bg-white/10"
                  }`}
                >
                  Todas as Fontes ({releases.length})
                </button>
                {availableSources.map((srcKey) => {
                  const count = releases.filter((r) => r.source_key === srcKey).length;
                  return (
                    <button
                      type="button"
                      key={srcKey}
                      onClick={() => {
                        setActiveSource(srcKey);
                        setFilterSeason("ALL");
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase whitespace-nowrap transition-colors cursor-pointer ${
                        activeSource === srcKey
                          ? "bg-emerald-500 text-slate-950"
                          : "bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                    >
                      {srcKey} ({count})
                    </button>
                  );
                })}
              </div>
            )}

            {seasons.length > 0 && (
              <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
                <button
                  type="button"
                  onClick={() => setFilterSeason("ALL")}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-colors cursor-pointer ${
                    filterSeason === "ALL"
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
                    className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${
                      filterSeason === s
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
        )}

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {!show.imdb_id ? (
            <div className="text-center py-12 text-slate-300">
              Esta obra não possui IMDb ID mapeado para consulta nas Fontes de Dados.
            </div>
          ) : loading ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <div className="w-8 h-8 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-300">
                Consultando indexadores em sources.db e provedores externos...
              </p>
            </div>
          ) : displayedReleases.length === 0 ? (
            <div className="text-center py-12 text-slate-300">
              Nenhuma fonte ou magnet encontrado para este filtro no momento.
            </div>
          ) : (
            displayedReleases.map((r) => (
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
                  {r.magnet_url && (
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
                  {r.external_url && (
                    <a
                      href={r.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-xs font-bold transition-colors"
                    >
                      <ExternalLink className="w-4 h-4" />
                      Ver Link
                    </a>
                  )}
                  {!r.magnet_url && r.torrent_url && (
                    <a
                      href={r.torrent_url}
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
            ))
          )}
        </div>
      </div>
    </div>
  );
};
