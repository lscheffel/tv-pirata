import React, { useState, useEffect } from "react";
import {
  X,
  Star,
  Calendar,
  Download,
  Bookmark,
  CheckCircle2,
  Circle,
  HardDrive,
  CheckCheck,
  Check,
} from "lucide-react";
import { UnifiedShow, UnifiedSeason } from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";

interface ShowDetailModalProps {
  show: UnifiedShow | null;
  onClose: () => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  isSaved?: boolean;
}

export const ShowDetailModal: React.FC<ShowDetailModalProps> = ({
  show,
  onClose,
  onOpenTorrents,
  onSaveToLibrary,
  isSaved = false,
}) => {
  const { showToast } = useToast();
  const [activeSeasonNum, setActiveSeasonNum] = useState<number>(1);
  const [fullShow, setFullShow] = useState<UnifiedShow | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [watchedEpisodeIds, setWatchedEpisodeIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!show) return;

    let isMounted = true;
    setLoading(true);

    api.discovery
      .getShowDetails(show.id, show.source_provider, show.imdb_id)
      .then((data) => {
        if (!isMounted) return;
        setFullShow(data);
        if (data.seasons && data.seasons.length > 0) {
          // Select first valid season number (usually season 1)
          const firstNonZero = data.seasons.find((s) => s.season_number > 0);
          setActiveSeasonNum(firstNonZero ? firstNonZero.season_number : data.seasons[0].season_number);

          // Populate watched state if present in episodes
          const watched = new Set<number>();
          data.seasons.forEach((season) => {
            season.episodes.forEach((ep) => {
              if (ep.is_watched && ep.id) {
                watched.add(ep.id);
              }
            });
          });
          setWatchedEpisodeIds(watched);
        }
      })
      .catch((err) => {
        console.error("Erro ao carregar detalhes completos:", err);
        // Fallback to passed show
        setFullShow(show);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [show]);

  if (!show) return null;

  const currentShow = fullShow || show;
  const currentSeason =
    currentShow.seasons.find((s) => s.season_number === activeSeasonNum) ||
    currentShow.seasons[0];

  const handleToggleEpisode = async (episodeId?: number) => {
    if (!episodeId) {
      showToast("Episódio sem ID registrado na biblioteca", "info");
      return;
    }

    // Optimistic toggle
    const isCurrentlyWatched = watchedEpisodeIds.has(episodeId);
    setWatchedEpisodeIds((prev) => {
      const next = new Set(prev);
      if (isCurrentlyWatched) {
        next.delete(episodeId);
      } else {
        next.add(episodeId);
      }
      return next;
    });

    try {
      const res = await api.watches.toggleEpisode(episodeId);
      showToast(
        res.is_watched ? "Episódio marcado como assistido!" : "Episódio desmarcado",
        "success"
      );
    } catch {
      // Revert optimistic update
      setWatchedEpisodeIds((prev) => {
        const next = new Set(prev);
        if (isCurrentlyWatched) {
          next.add(episodeId);
        } else {
          next.delete(episodeId);
        }
        return next;
      });
      showToast("Falha ao atualizar status do episódio", "error");
    }
  };

  const handleWatchAllSeason = async (season: UnifiedSeason) => {
    if (!season.id) {
      showToast("Temporada ainda não sincronizada no banco relacional", "info");
      return;
    }

    try {
      await api.watches.watchAllSeason(season.id, true);
      // Mark all episodes in season as watched locally
      setWatchedEpisodeIds((prev) => {
        const next = new Set(prev);
        season.episodes.forEach((ep) => {
          if (ep.id) next.add(ep.id);
        });
        return next;
      });
      showToast(`Temporada ${season.season_number} marcada como assistida!`, "success");
    } catch {
      showToast("Erro ao marcar temporada como assistida", "error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-surface rounded-2xl border border-white/10 shadow-2xl overflow-hidden my-auto max-h-[92vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-30 p-2 rounded-full bg-black/60 text-slate-300 hover:text-white hover:bg-black/80 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Hero Header Area */}
        <div className="relative h-64 sm:h-80 w-full shrink-0 overflow-hidden bg-surface-elevated">
          {currentShow.backdrop_url && (
            <img
              src={currentShow.backdrop_url}
              alt={currentShow.title}
              className="w-full h-full object-cover object-top filter brightness-[0.75]"
            />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-surface via-surface/60 to-transparent" />

          {/* Header Content */}
          <div className="absolute inset-x-0 bottom-0 p-6 flex flex-col justify-end">
            <div className="flex flex-wrap items-center gap-2 mb-2 text-xs">
              {currentShow.rating > 0 && (
                <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-cinema-gold/20 text-yellow-300 font-bold border border-cinema-gold/30">
                  <Star className="w-3.5 h-3.5 fill-yellow-400" />
                  {currentShow.rating.toFixed(1)}
                </span>
              )}
              {currentShow.first_air_date && (
                <span className="flex items-center gap-1 text-slate-300 font-medium">
                  <Calendar className="w-3 h-3 text-slate-400" />
                  {new Date(currentShow.first_air_date).getFullYear()}
                </span>
              )}
              {currentShow.genres.map((g) => (
                <span key={g} className="px-2 py-0.5 rounded-full bg-white/10 text-slate-300 text-xs">
                  {g}
                </span>
              ))}
            </div>

            <h2 className="text-2xl sm:text-4xl font-extrabold text-white drop-shadow">
              {currentShow.title}
            </h2>

            {/* Actions Bar */}
            <div className="flex flex-wrap items-center gap-3 mt-4">
              {currentShow.imdb_id && (
                <button
                  onClick={() => onOpenTorrents(currentShow)}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-red hover:bg-brand-redHover text-white font-bold text-sm shadow-cinema-glow transition-all active:scale-95"
                >
                  <Download className="w-4 h-4" />
                  Obter Torrents (EZTV)
                </button>
              )}

              {onSaveToLibrary && (
                <button
                  onClick={() => onSaveToLibrary(currentShow)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all ${
                    isSaved
                      ? "bg-emerald-950/60 border-emerald-500/50 text-emerald-300"
                      : "bg-surface-elevated/80 border-white/20 text-slate-200 hover:bg-white/10"
                  }`}
                >
                  {isSaved ? <Check className="w-4 h-4 text-emerald-400" /> : <Bookmark className="w-4 h-4" />}
                  {isSaved ? "Salva na Biblioteca" : "Adicionar à Minha Lista"}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Scrollable Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Overview */}
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Sinopse
            </h4>
            <p className="text-sm text-slate-300 leading-relaxed">
              {currentShow.overview || "Nenhuma sinopse disponível para este título."}
            </p>
          </div>

          {/* Season Selector Tabs */}
          {currentShow.seasons && currentShow.seasons.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <div className="flex gap-2 overflow-x-auto no-scrollbar py-1">
                  {currentShow.seasons.map((season) => (
                    <button
                      key={season.season_number}
                      onClick={() => setActiveSeasonNum(season.season_number)}
                      className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all ${
                        activeSeasonNum === season.season_number
                          ? "bg-white text-black shadow-md font-bold"
                          : "text-slate-400 hover:text-white hover:bg-white/5"
                      }`}
                    >
                      {season.season_number === 0 ? "Especiais" : `Temporada ${season.season_number}`}
                    </button>
                  ))}
                </div>

                {currentSeason && currentSeason.episodes.length > 0 && (
                  <button
                    onClick={() => handleWatchAllSeason(currentSeason)}
                    className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-emerald-400 transition-colors shrink-0 font-medium px-2 py-1 rounded bg-white/5 hover:bg-white/10"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    Marcar Temporada Toda
                  </button>
                )}
              </div>

              {/* Episodes List */}
              {loading ? (
                <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
                  Carregando lista de episódios...
                </div>
              ) : currentSeason && currentSeason.episodes && currentSeason.episodes.length > 0 ? (
                <div className="space-y-2">
                  {currentSeason.episodes.map((ep) => {
                    const isWatched = ep.id ? watchedEpisodeIds.has(ep.id) : false;

                    return (
                      <div
                        key={ep.episode_number}
                        className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                          isWatched
                            ? "bg-emerald-950/20 border-emerald-500/30 text-slate-200"
                            : "bg-surface-elevated/40 border-white/5 hover:border-white/15 text-slate-300"
                        }`}
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0 pr-3">
                          <button
                            onClick={() => handleToggleEpisode(ep.id)}
                            className="p-1 hover:scale-110 active:scale-95 transition-transform"
                          >
                            {isWatched ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-400 fill-emerald-500/20" />
                            ) : (
                              <Circle className="w-5 h-5 text-slate-500 hover:text-white" />
                            )}
                          </button>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono font-bold text-slate-400 shrink-0">
                                #{ep.episode_number.toString().padStart(2, "0")}
                              </span>
                              <span className="text-sm font-semibold text-white truncate">
                                {ep.title || `Episódio ${ep.episode_number}`}
                              </span>
                              {ep.is_available && (
                                <span
                                  title="Disponível no servidor SMB local"
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                >
                                  <HardDrive className="w-2.5 h-2.5" />
                                  SMB
                                </span>
                              )}
                            </div>
                            {ep.overview && (
                              <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                                {ep.overview}
                              </p>
                            )}
                          </div>
                        </div>

                        {ep.air_date && (
                          <span className="text-xs text-slate-500 shrink-0">
                            {new Date(ep.air_date).toLocaleDateString("pt-BR")}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="py-6 text-center text-slate-500 text-sm">
                  Nenhum episódio cadastrado para esta temporada.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

