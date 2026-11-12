import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Bookmark, Star, Trash2, Download, Info, Bell, RefreshCw, CheckCheck, Sparkles } from "lucide-react";
import { ShowRecord, UnifiedShow, ReleaseNotification } from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";

interface LibraryViewProps {
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onNotificationsChange?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  all: "Todos",
  watching: "Assistindo",
  plan_to_watch: "Quero Ver",
  completed: "Concluído",
  paused: "Pausado",
  abandoned: "Abandonado",
};

export const LibraryView: React.FC<LibraryViewProps> = ({
  onOpenDetails,
  onOpenTorrents,
  onNotificationsChange,
}) => {
  const { showToast } = useToast();
  const [shows, setShows] = useState<ShowRecord[]>([]);
  const [notifications, setNotifications] = useState<ReleaseNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const loadNotifications = useCallback(async () => {
    try {
      const data = await api.notifications.list(true);
      setNotifications(data);
      if (onNotificationsChange) {
        onNotificationsChange();
      }
    } catch (err) {
      console.error("Erro ao carregar notificações:", err);
    }
  }, [onNotificationsChange]);

  const loadLibrary = useCallback(() => {
    setLoading(true);
    api.library
      .getShows()
      .then((data) => setShows(data))
      .catch((err) => {
        console.error("Erro ao carregar biblioteca:", err);
        showToast("Erro ao carregar séries da biblioteca", "error");
      })
      .finally(() => setLoading(false));
  }, [showToast]);

  useEffect(() => {
    loadLibrary();
    loadNotifications();
  }, [loadLibrary, loadNotifications]);

  const notificationsByShowId = useMemo(() => {
    const map: Record<number, ReleaseNotification[]> = {};
    for (const notif of notifications) {
      if (!map[notif.show_id]) {
        map[notif.show_id] = [];
      }
      map[notif.show_id].push(notif);
    }
    return map;
  }, [notifications]);

  const handleStatusChange = async (showId: number, newStatus: string) => {
    try {
      await api.library.updateStatus(showId, newStatus);
      setShows((prev) =>
        prev.map((s) => (s.id === showId ? { ...s, user_status: newStatus as any } : s))
      );
      showToast(`Status atualizado para "${STATUS_LABELS[newStatus] || newStatus}"`, "success");
    } catch {
      showToast("Erro ao atualizar status", "error");
    }
  };

  const handleDelete = async (showId: number, title: string) => {
    if (!window.confirm(`Tem certeza que deseja remover "${title}" da sua biblioteca?`)) {
      return;
    }
    try {
      await api.library.deleteShow(showId);
      setShows((prev) => prev.filter((s) => s.id !== showId));
      showToast(`"${title}" removida da biblioteca`, "info");
      loadNotifications();
    } catch {
      showToast("Erro ao remover série", "error");
    }
  };

  const handleTriggerSync = async () => {
    setSyncing(true);
    try {
      await api.notifications.triggerSync();
      showToast("Sincronização iniciada em background!", "info");
      // Espera 2.5s para recarregar as notificações encontradas
      setTimeout(async () => {
        await loadNotifications();
        setSyncing(false);
      }, 2500);
    } catch {
      showToast("Falha ao disparar sincronização manual", "error");
      setSyncing(false);
    }
  };

  const handleDismissAll = async () => {
    try {
      await api.notifications.dismissAll();
      setNotifications([]);
      showToast("Todos os alertas foram dispensados", "info");
      if (onNotificationsChange) {
        onNotificationsChange();
      }
    } catch {
      showToast("Erro ao dispensar alertas", "error");
    }
  };

  const handleMarkNotificationRead = async (notifId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.notifications.markAsRead(notifId);
      setNotifications((prev) => prev.filter((n) => n.id !== notifId));
      if (onNotificationsChange) {
        onNotificationsChange();
      }
    } catch {
      showToast("Erro ao marcar notificação", "error");
    }
  };

  const filteredShows =
    filterStatus === "all"
      ? shows
      : shows.filter((s) => s.user_status === filterStatus);

  const convertToUnified = (s: ShowRecord): UnifiedShow => ({
    id: s.tmdb_id || s.id,
    tmdb_id: s.tmdb_id,
    tvmaze_id: s.tvmaze_id || undefined,
    imdb_id: s.imdb_id || undefined,
    title: s.title,
    original_title: s.original_title || undefined,
    overview: s.overview,
    poster_url: s.poster_url || undefined,
    backdrop_url: s.backdrop_url || undefined,
    rating: s.rating,
    genres: s.genres ? s.genres.split(",").map((g) => g.trim()) : [],
    first_air_date: s.first_air_date || undefined,
    status: s.status || undefined,
    source_provider: "library",
    seasons: [],
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
            <Bookmark className="w-8 h-8 text-brand-red" />
            Minha Biblioteca
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Seu acervo gerenciado e acompanhado com sincronização em background
          </p>
        </div>

        {/* Global Action & Filter Chips */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleTriggerSync}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-surface-elevated text-slate-300 hover:text-white hover:bg-surface-highlight border border-white/10 transition-all disabled:opacity-50"
            title="Verificar novos lançamentos no EZTV agora"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin text-brand-red" : ""}`} />
            <span>{syncing ? "Sincronizando..." : "Verificar Agora"}</span>
          </button>

          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilterStatus(key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                filterStatus === key
                  ? "bg-brand-red text-white shadow-cinema-glow"
                  : "bg-surface-elevated text-slate-400 hover:text-white hover:bg-surface-highlight border border-white/5"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Release Notification Banner */}
      {notifications.length > 0 && (
        <div className="mb-8 p-4 rounded-2xl bg-gradient-to-r from-brand-red/20 via-surface-elevated to-surface-elevated border border-brand-red/30 shadow-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-red text-white shadow-cinema-glow">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                Novos Episódios Detectados!
                <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-brand-red text-white">
                  {notifications.length} {notifications.length === 1 ? "release" : "releases"}
                </span>
              </h2>
              <p className="text-xs text-slate-300 mt-0.5">
                O motor em segundo plano identificou novos episódios para suas séries acompanhadas.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              onClick={handleDismissAll}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/10 hover:bg-white/20 text-white transition-colors"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              Dispensar Todos
            </button>
          </div>
        </div>
      )}

      {/* Grid of Shows */}
      {loading ? (
        <div className="py-20 text-center text-slate-500 animate-pulse">
          Carregando acervo pessoal...
        </div>
      ) : filteredShows.length === 0 ? (
        <div className="py-24 text-center rounded-2xl border border-dashed border-white/10 bg-surface/40 p-8 space-y-3">
          <Bookmark className="w-12 h-12 mx-auto text-slate-600" />
          <h3 className="text-lg font-bold text-slate-300">Nenhuma série encontrada</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            Navegue pela aba &quot;Descobrir&quot; ou &quot;Catálogo EZTV&quot; e clique no botão &quot;Adicionar à Minha Lista&quot; em qualquer título!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-6">
          {filteredShows.map((show) => {
            const unified = convertToUnified(show);
            const showNotifs = notificationsByShowId[show.id] || [];
            const hasNewReleases = showNotifs.length > 0;

            return (
              <div
                key={show.id}
                className={`group relative flex flex-col rounded-xl overflow-hidden bg-surface border transition-all hover:scale-[1.02] shadow-xl ${
                  hasNewReleases
                    ? "border-brand-red/50 shadow-brand-red/10"
                    : "border-white/5 hover:border-white/15"
                }`}
              >
                {/* Poster */}
                <div
                  onClick={() => onOpenDetails(unified)}
                  className="relative aspect-[2/3] w-full bg-surface-elevated cursor-pointer overflow-hidden"
                >
                  {show.poster_url ? (
                    <img
                      src={show.poster_url}
                      alt={show.title}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center p-4 text-center text-xs text-slate-500 font-bold">
                      {show.title}
                    </div>
                  )}

                  {/* Rating Badge */}
                  {show.rating > 0 && (
                    <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/75 backdrop-blur-md text-yellow-400 text-xs font-bold border border-yellow-500/20">
                      <Star className="w-3 h-3 fill-yellow-400" />
                      {show.rating.toFixed(1)}
                    </div>
                  )}

                  {/* New Episode Notification Ribbon */}
                  {hasNewReleases && (
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenTorrents(unified);
                      }}
                      className="absolute bottom-2 left-2 right-2 flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-brand-red text-white text-[11px] font-black shadow-cinema-glow cursor-pointer hover:bg-red-700 transition-colors"
                      title="Clique para abrir torrents dos novos episódios"
                    >
                      <span className="flex items-center gap-1 truncate">
                        <Bell className="w-3 h-3 shrink-0 animate-bounce" />
                        {showNotifs.length === 1
                          ? `Novo: S${String(showNotifs[0].season).padStart(2, "0")}E${String(showNotifs[0].episode).padStart(2, "0")}`
                          : `${showNotifs.length} novos episódios`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={(e) => handleMarkNotificationRead(showNotifs[0].id, e)}
                          title="Marcar alerta como visto"
                          className="p-0.5 hover:text-black hover:bg-white/20 rounded transition-colors"
                        >
                          <CheckCheck className="w-3 h-3 shrink-0" />
                        </button>
                        <Download className="w-3 h-3 shrink-0" />
                      </div>
                    </div>
                  )}
                </div>

                {/* Info & Status */}
                <div className="p-3 flex flex-col flex-1 justify-between gap-2">
                  <div>
                    <h3
                      onClick={() => onOpenDetails(unified)}
                      className="text-sm font-bold text-white line-clamp-1 cursor-pointer hover:text-brand-red transition-colors"
                    >
                      {show.title}
                    </h3>

                    {/* Status Dropdown */}
                    <div className="mt-2">
                      <select
                        value={show.user_status}
                        onChange={(e) => handleStatusChange(show.id, e.target.value)}
                        className="w-full bg-surface-elevated border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200 font-medium focus:outline-none focus:border-brand-red cursor-pointer"
                      >
                        <option value="watching">Assistindo</option>
                        <option value="plan_to_watch">Quero Ver</option>
                        <option value="completed">Concluído</option>
                        <option value="paused">Pausado</option>
                        <option value="abandoned">Abandonado</option>
                      </select>
                    </div>
                  </div>

                  {/* Quick Card Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-white/5">
                    <div className="flex items-center gap-1">
                      <button
                        title="Ver Detalhes"
                        onClick={() => onOpenDetails(unified)}
                        className="p-1.5 rounded-lg bg-surface-elevated text-slate-300 hover:text-white transition-colors"
                      >
                        <Info className="w-3.5 h-3.5" />
                      </button>

                      {show.imdb_id && (
                        <button
                          title="Obter Torrents"
                          onClick={() => onOpenTorrents(unified)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            hasNewReleases
                              ? "bg-brand-red text-white shadow-cinema-glow"
                              : "bg-brand-red/20 text-brand-red hover:bg-brand-red hover:text-white"
                          }`}
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <button
                      title="Remover da Biblioteca"
                      onClick={() => handleDelete(show.id, show.title)}
                      className="p-1.5 text-slate-500 hover:text-brand-red transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
