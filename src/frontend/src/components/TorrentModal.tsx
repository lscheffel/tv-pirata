import React, { useState, useEffect, useMemo } from "react";
import {
  X,
  Download,
  Copy,
  Check,
  ExternalLink,
  Users,
  HardDrive,
  Filter,
} from "lucide-react";
import { TorrentRelease, UnifiedShow } from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";

interface TorrentModalProps {
  show: UnifiedShow | null;
  onClose: () => void;
}

export const TorrentModal: React.FC<TorrentModalProps> = ({ show, onClose }) => {
  const { showToast } = useToast();
  const [torrents, setTorrents] = useState<TorrentRelease[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [selectedQuality, setSelectedQuality] = useState<string>("ALL");

  useEffect(() => {
    if (!show || !show.imdb_id) return;

    let isMounted = true;
    setLoading(true);

    api.torrents
      .getByImdb(show.imdb_id)
      .then((data) => {
        if (!isMounted) return;
        setTorrents(data);
      })
      .catch((err) => {
        console.error("Erro ao buscar torrents:", err);
        showToast("Erro ao conectar à API de torrents EZTV", "error");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [show, showToast]);

  if (!show) return null;

  const formatSize = (bytes: number) => {
    if (!bytes || bytes === 0) return "Tamanho N/D";
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(2)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  const handleCopyMagnet = async (magnet: string, hash: string) => {
    try {
      await navigator.clipboard.writeText(magnet);
      setCopiedHash(hash);
      showToast("Magnet Link copiado para a área de transferência!", "success");
      setTimeout(() => setCopiedHash(null), 3000);
    } catch {
      showToast("Não foi possível copiar automaticamente para o clipboard", "error");
    }
  };

  // Distinct qualities available
  const availableQualities = useMemo(() => {
    const set = new Set<string>();
    torrents.forEach((t) => {
      if (t.quality) set.add(t.quality);
    });
    return ["ALL", ...Array.from(set)];
  }, [torrents]);

  // Filtered releases
  const filteredTorrents = useMemo(() => {
    if (selectedQuality === "ALL") return torrents;
    return torrents.filter((t) => t.quality === selectedQuality);
  }, [torrents, selectedQuality]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-surface rounded-2xl border border-white/10 shadow-2xl overflow-hidden my-auto max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-surface-elevated/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-red/20 text-brand-red border border-brand-red/30">
              <Download className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg sm:text-xl font-bold text-white line-clamp-1">
                  Torrents EZTV: {show.title}
                </h3>
                <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-slate-300 font-mono font-bold">
                  {show.imdb_id}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Magnets verificados e ordenados pela API pública da EZTV
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quality Filter Bar */}
        <div className="px-6 py-3 bg-surface border-b border-white/5 flex items-center justify-between gap-3 overflow-x-auto no-scrollbar">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400 shrink-0" />
            <span className="text-xs font-semibold text-slate-400 shrink-0">Filtrar Resolução:</span>
            <div className="flex gap-1.5">
              {availableQualities.map((q) => (
                <button
                  key={q}
                  onClick={() => setSelectedQuality(q)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    selectedQuality === q
                      ? "bg-brand-red text-white shadow-cinema-glow"
                      : "bg-surface-elevated text-slate-400 hover:text-white hover:bg-surface-highlight"
                  }`}
                >
                  {q === "ALL" ? "Todas" : q}
                </button>
              ))}
            </div>
          </div>

          <span className="text-xs text-slate-400 shrink-0">
            {filteredTorrents.length} releases encontradas
          </span>
        </div>

        {/* Torrents List */}
        <div className="p-6 overflow-y-auto space-y-3 flex-1">
          {loading ? (
            <div className="py-12 text-center text-slate-500 animate-pulse space-y-2">
              <Download className="w-8 h-8 mx-auto text-brand-red animate-bounce" />
              <p className="text-sm">Buscando releases na rede EZTV...</p>
            </div>
          ) : filteredTorrents.length === 0 ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <p className="text-base font-semibold">Nenhuma release encontrada para este título.</p>
              <p className="text-xs text-slate-500">
                Verifique se o IMDB ID está cadastrado ou tente buscar por outro título.
              </p>
            </div>
          ) : (
            filteredTorrents.map((torrent) => {
              const isCopied = copiedHash === torrent.hash;

              return (
                <div
                  key={`${torrent.id}-${torrent.hash}`}
                  className="p-4 rounded-xl bg-surface-elevated/60 border border-white/5 hover:border-white/15 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      {/* Quality Badge */}
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-bold ${
                          torrent.quality.includes("4K")
                            ? "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                            : torrent.quality.includes("1080p")
                            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                            : "bg-white/10 text-slate-300"
                        }`}
                      >
                        {torrent.quality}
                      </span>

                      {/* Episode details if season/episode > 0 */}
                      {torrent.season > 0 && (
                        <span className="text-xs font-mono font-semibold text-slate-300 bg-surface-highlight px-2 py-0.5 rounded">
                          S{torrent.season.toString().padStart(2, "0")}E
                          {torrent.episode.toString().padStart(2, "0")}
                        </span>
                      )}

                      {/* Seeds & Peers Badges */}
                      <span className="flex items-center gap-1 text-xs text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        <Users className="w-3 h-3" />
                        {torrent.seeds} seeds
                      </span>

                      <span className="text-xs text-slate-400">
                        {torrent.peers} peers
                      </span>

                      <span className="flex items-center gap-1 text-xs text-slate-400">
                        <HardDrive className="w-3 h-3 text-slate-500" />
                        {formatSize(torrent.size_bytes)}
                      </span>
                    </div>

                    {/* Torrent Title / Filename */}
                    <h4 className="text-sm font-semibold text-white truncate group-hover:text-cyan-300 transition-colors">
                      {torrent.title || torrent.filename}
                    </h4>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 justify-end">
                    {/* Copy Magnet 1-Click */}
                    <button
                      onClick={() => handleCopyMagnet(torrent.magnet_url, torrent.hash)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                        isCopied
                          ? "bg-emerald-600 text-white"
                          : "bg-white/10 hover:bg-white/20 text-white"
                      }`}
                    >
                      {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      {isCopied ? "Copiado!" : "Copiar Magnet"}
                    </button>

                    {/* Direct Magnet Protocol Link */}
                    <a
                      href={torrent.magnet_url}
                      title="Abrir no cliente de torrent padrão"
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold bg-brand-red hover:bg-brand-redHover text-white transition-all shadow-cinema-glow"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      Baixar
                    </a>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

