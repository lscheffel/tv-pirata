import React, { useEffect, useRef, useState } from "react";
import {
  Bookmark,
  Check,
  FolderPlus,
  Magnet,
  MoreVertical,
  Star,
  X,
} from "lucide-react";
import { UnifiedShow } from "../types";
import { useExplorePreferences } from "../context/PreferencesContext";
import { useToast } from "../context/ToastContext";
import { MediaBadge } from "./MediaBadge";
import { ProviderBadge, StatusBadge } from "./ShowBadges";

interface ShowCardProps {
  show: UnifiedShow;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  onAddToCollection?: (show: UnifiedShow) => void;
  onFilterProvider?: (provider: string) => void;
  onFilterHasMedia?: () => void;
  isSaved?: boolean;
  fluidWidth?: boolean;
  workTypeLabel?: string;
  runtimeMinutes?: number | null;
  originCountry?: string | null;
  directors?: string[];
  extraStatusLabel?: string;
}

export const ShowCard: React.FC<ShowCardProps> = ({
  show,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  onAddToCollection,
  onFilterProvider,
  onFilterHasMedia,
  isSaved = false,
  fluidWidth = false,
  workTypeLabel,
  runtimeMinutes,
  originCountry,
  directors,
  extraStatusLabel,
}) => {
  const { preferences } = useExplorePreferences();
  const { showToast } = useToast();
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardWidth, setCardWidth] = useState<number>(220);
  const [providersExpanded, setProvidersExpanded] = useState<boolean>(false);
  const [actionsOpen, setActionsOpen] = useState<boolean>(false);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.getBoundingClientRect().width;
      if (w > 0) setCardWidth(w);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setCardWidth(entry.contentRect.width);
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const year = show.first_air_date ? String(show.first_air_date).slice(0, 4) : "";
  const providersList = Array.from(
    new Set(
      show.streaming_providers && show.streaming_providers.length > 0
        ? show.streaming_providers
        : show.network
          ? [show.network]
          : []
    )
  );
  const hasMedia = Boolean(
    show.has_media || show.eztv_available || (show.media_sources && show.media_sources.length > 0)
  );
  const mediaSources =
    show.media_sources && show.media_sources.length > 0
      ? show.media_sources
      : show.eztv_available
        ? ["eztv"]
        : [];

  // Responsive safeguard (AUD-CRIT-01): full vertical stack on >=190px, 1+N on <190px mobile
  const isNarrowCard = cardWidth < 190;
  const visibleProviders =
    isNarrowCard && !providersExpanded ? providersList.slice(0, 1) : providersList;
  const hiddenProvidersCount = Math.max(0, providersList.length - visibleProviders.length);

  const getProviderTooltip = (prov: string): string => {
    if (preferences.badge_provider_action === "filter_provider") {
      return `${prov} — clique para filtrar catálogo por este provedor`;
    }
    if (preferences.badge_provider_action === "open_provider_info") {
      return `${prov} — clique para ver disponibilidade e detalhes`;
    }
    return `${prov} — clique para abrir detalhes do título`;
  };

  const handleProviderClick = (prov: string) => {
    if (preferences.badge_provider_action === "filter_provider" && onFilterProvider) {
      onFilterProvider(prov);
      return;
    }
    if (preferences.badge_provider_action === "open_provider_info") {
      showToast(`Disponibilidade: ${prov} • Abrindo detalhes de "${show.title}"`, "info");
    }
    onOpenDetails(show);
  };

  const getMediaTooltip = (): string => {
    const srcTxt =
      mediaSources.length > 0 ? mediaSources.map((s) => s.toUpperCase()).join(", ") : "Fontes";
    if (preferences.badge_media_action === "open_sources_modal") {
      return `Media (${srcTxt}) — clique para abrir fontes disponíveis`;
    }
    if (preferences.badge_media_action === "filter_has_media") {
      return `Media (${srcTxt}) — clique para filtrar obras com mídia disponível`;
    }
    return `Media (${srcTxt}) — clique para abrir detalhes do título`;
  };

  const handleMediaBadgeClick = () => {
    if (preferences.badge_media_action === "filter_has_media" && onFilterHasMedia) {
      onFilterHasMedia();
      return;
    }
    if (preferences.badge_media_action === "open_details") {
      onOpenDetails(show);
      return;
    }
    if (show.imdb_id) {
      onOpenTorrents(show);
    } else {
      onOpenDetails(show);
    }
  };

  const widthClasses = fluidWidth ? "w-full" : "w-[160px] sm:w-[190px] md:w-[220px] shrink-0";

  return (
    <article
      ref={cardRef}
      onClick={() => onOpenDetails(show)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpenDetails(show);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`Abrir detalhes de ${show.title}`}
      className={`group relative flex flex-col text-left ${widthClasses} rounded-xl overflow-hidden bg-surface hover:bg-surface-hover border border-white/10 hover:border-brand-red/60 transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl cursor-pointer select-none`}
    >
      {/* Poster Container */}
      <div className="relative aspect-[2/3] w-full overflow-hidden bg-surface-elevated">
        {show.poster_url ? (
          <img
            src={show.poster_url}
            alt={show.title}
            loading="lazy"
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center bg-gradient-to-br from-surface-elevated to-canvas">
            <span className="text-sm font-bold text-slate-200 line-clamp-2">{show.title}</span>
            <span className="text-xs text-slate-300 mt-1">{year || "Sem capa"}</span>
          </div>
        )}

        {/* Top Vignette & Bottom Vignette for guaranteed >=4.5:1 badge readability */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/75 to-transparent" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/90 via-black/45 to-transparent" />

        {/* Top-Left: Optional Work Type Badge */}
        {workTypeLabel && (
          <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-extrabold uppercase tracking-wider text-slate-100 border border-white/15">
            {workTypeLabel}
          </div>
        )}

        {/* Top-Right: IMDb Rating + MediaBadge directly below it */}
        <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
          {show.rating > 0 &&
            (show.imdb_id ? (
              <a
                href={`https://www.imdb.com/title/${encodeURIComponent(show.imdb_id)}/`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                title={`Abrir ${show.title} no IMDb (${show.imdb_id})`}
                aria-label={`Abrir ${show.title} no IMDb`}
                className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-yellow-300 text-xs font-bold border border-yellow-500/30 hover:bg-yellow-500/20 hover:border-yellow-400 transition-colors cursor-pointer"
              >
                <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                <span>{show.rating.toFixed(1)}</span>
              </a>
            ) : (
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-yellow-300 text-xs font-bold border border-yellow-500/30">
                <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                <span>{show.rating.toFixed(1)}</span>
              </div>
            ))}
          {hasMedia && (
            <MediaBadge
              compact={isNarrowCard}
              sources={mediaSources}
              onClick={handleMediaBadgeClick}
              title={getMediaTooltip()}
              ariaLabel={getMediaTooltip()}
            />
          )}
        </div>

        {/* Bottom-Left: Providers stacked vertically ABOVE StatusBadge (1+N safeguard on <190px) */}
        {(providersList.length > 0 || show.status) && (
          <div className="absolute bottom-2 left-2 z-10 max-w-[calc(100%-60px)] flex flex-col items-start gap-1">
            {visibleProviders.length > 0 && (
              <div className="flex flex-col items-start gap-1">
                {visibleProviders.map((prov) => (
                  <ProviderBadge
                    key={prov}
                    provider={prov}
                    compact={isNarrowCard}
                    onClick={() => handleProviderClick(prov)}
                    title={getProviderTooltip(prov)}
                    ariaLabel={getProviderTooltip(prov)}
                  />
                ))}
                {hiddenProvidersCount > 0 && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setProvidersExpanded(true);
                    }}
                    title={`Exibir mais ${hiddenProvidersCount} serviço(s): ${providersList
                      .slice(1)
                      .join(", ")}`}
                    aria-label={`Exibir mais ${hiddenProvidersCount} provedores de streaming`}
                    className="inline-flex items-center px-1.5 py-0.5 rounded-md border border-white/25 bg-black/85 text-slate-100 text-[9px] font-extrabold hover:bg-white/20 cursor-pointer"
                  >
                    +{hiddenProvidersCount}
                  </button>
                )}
              </div>
            )}
            <StatusBadge status={show.status} compact={isNarrowCard} />
          </div>
        )}

        {/* Bottom-Right: Expandable Tactile 44x44px Quick Action Button */}
        <div
          className="absolute bottom-1.5 right-1.5 z-20 flex flex-col items-end gap-1.5"
          onClick={(e) => e.stopPropagation()}
        >
          {actionsOpen && (
            <div
              role="menu"
              aria-label={`Ações rápidas para ${show.title}`}
              className="flex flex-col items-end gap-1.5 p-1.5 rounded-xl bg-surface-elevated/95 border border-white/20 shadow-2xl backdrop-blur-md"
            >
              {onSaveToLibrary && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    onSaveToLibrary(show);
                    setActionsOpen(false);
                  }}
                  aria-label={isSaved ? "Já salva na Biblioteca" : "Salvar na Biblioteca"}
                  className={`min-h-[44px] px-3 rounded-lg flex items-center gap-2 text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${
                    isSaved
                      ? "bg-emerald-600 text-white"
                      : "bg-canvas hover:bg-brand-red text-slate-100"
                  }`}
                >
                  {isSaved ? <Check className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                  <span>{isSaved ? "Na Lista" : "Biblioteca"}</span>
                </button>
              )}

              {show.imdb_id && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    onOpenTorrents(show);
                    setActionsOpen(false);
                  }}
                  aria-label="Abrir fontes de mídia e downloads"
                  className="min-h-[44px] px-3 rounded-lg bg-canvas hover:bg-emerald-600 text-slate-100 flex items-center gap-2 text-xs font-bold whitespace-nowrap transition-colors cursor-pointer"
                >
                  <Magnet className="w-4 h-4" />
                  <span>Fontes Media</span>
                </button>
              )}

              {onAddToCollection && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    onAddToCollection(show);
                    setActionsOpen(false);
                  }}
                  aria-label="Adicionar à coleção"
                  className="min-h-[44px] px-3 rounded-lg bg-canvas hover:bg-sky-600 text-slate-100 flex items-center gap-2 text-xs font-bold whitespace-nowrap transition-colors cursor-pointer"
                >
                  <FolderPlus className="w-4 h-4" />
                  <span>Coleções</span>
                </button>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => setActionsOpen((prev) => !prev)}
            aria-expanded={actionsOpen}
            aria-label={actionsOpen ? "Fechar ações rápidas" : "Abrir ações rápidas"}
            title={actionsOpen ? "Fechar ações rápidas" : "Ações rápidas (Biblioteca, Fontes, Coleções)"}
            className={`min-w-[44px] min-h-[44px] rounded-full flex items-center justify-center border backdrop-blur-md transition-colors cursor-pointer shadow-lg ${
              actionsOpen
                ? "bg-brand-red text-white border-brand-red"
                : "bg-black/80 text-slate-100 border-white/25 hover:bg-brand-red hover:border-brand-red"
            }`}
          >
            {actionsOpen ? <X className="w-4 h-4" /> : <MoreVertical className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Card Footer Info (>= 4.5:1 contrast with slate-300) */}
      <div className="p-3 flex flex-col justify-between flex-1 gap-1.5">
        <div>
          <h3 className="text-sm font-bold text-white line-clamp-1 group-hover:text-brand-red transition-colors">
            {show.title}
          </h3>
          {show.original_title &&
            show.original_title.toLowerCase() !== show.title.toLowerCase() && (
              <p className="text-[11px] text-slate-300 line-clamp-1 italic">
                {show.original_title}
              </p>
            )}
          <div className="flex items-center gap-1.5 text-xs text-slate-300 mt-0.5">
            {year && <span>{year}</span>}
            {runtimeMinutes ? <span>• {runtimeMinutes}m</span> : null}
            {originCountry ? <span>• {originCountry}</span> : null}
            {!runtimeMinutes && !originCountry && year && show.genres.length > 0 && (
              <span className="truncate">• {show.genres[0]}</span>
            )}
          </div>
          {directors && directors.length > 0 && (
            <p className="text-[11px] text-slate-300 mt-0.5 line-clamp-1">
              Dir: <span className="font-semibold text-white">{directors.join(", ")}</span>
            </p>
          )}
        </div>

        {(show.genres.length > 0 || isSaved || extraStatusLabel) && (
          <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-white/10">
            {show.genres.slice(0, 2).map((g) => (
              <span
                key={g}
                className="text-[10px] px-1.5 py-0.5 rounded bg-surface-elevated text-slate-200 border border-white/5"
              >
                {g}
              </span>
            ))}
            {extraStatusLabel && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-200 font-bold">
                {extraStatusLabel}
              </span>
            )}
            {isSaved && !extraStatusLabel && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                Na Lista
              </span>
            )}
          </div>
        )}
      </div>
    </article>
  );
};
