import React, { useEffect, useState } from "react";
import {
  Info,
  Download,
  Star,
  Calendar,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { UnifiedShow } from "../types";

export type HeroCandidate = UnifiedShow & { highlight_reason?: string };

interface HeroBannerProps {
  show: HeroCandidate | null;
  pool?: HeroCandidate[];
  autoRotate?: boolean;
  intervalSec?: number;
  onImpression?: (imdbId: string) => void;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary: (show: UnifiedShow) => void;
  isSaved?: boolean;
  savedShowIds?: Set<number>;
}

export const HeroBanner: React.FC<HeroBannerProps> = ({
  show,
  pool = [],
  autoRotate = true,
  intervalSec = 12,
  onImpression,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  isSaved = false,
  savedShowIds,
}) => {
  const candidates = pool.length > 0 ? pool : show ? [show] : [];
  const [activeIdx, setActiveIdx] = useState<number>(0);
  const [paused, setPaused] = useState<boolean>(false);

  useEffect(() => {
    if (activeIdx >= candidates.length) {
      setActiveIdx(0);
    }
  }, [candidates.length, activeIdx]);

  useEffect(() => {
    if (!autoRotate || paused || candidates.length <= 1) return;
    const ms = Math.max(5, intervalSec) * 1000;
    const timer = window.setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % candidates.length);
    }, ms);
    return () => window.clearInterval(timer);
  }, [autoRotate, paused, intervalSec, candidates.length]);

  const current = candidates[activeIdx] || show;

  useEffect(() => {
    const iid = current?.imdb_id;
    if (!iid || !onImpression) return;
    const t = window.setTimeout(() => onImpression(iid), 1800);
    return () => window.clearTimeout(t);
  }, [current?.imdb_id, onImpression]);

  if (!current) {
    return (
      <div className="relative h-[65vh] min-h-[480px] max-h-[720px] w-full bg-surface-elevated animate-pulse flex items-center justify-center">
        <span className="text-slate-500 font-medium">Carregando catálogo cinematográfico...</span>
      </div>
    );
  }

  const backdrop = current.backdrop_url || current.poster_url || "";
  const year = current.first_air_date ? new Date(current.first_air_date).getFullYear() : "";
  const currentSaved = savedShowIds
    ? savedShowIds.has(current.id) || (current.tmdb_id ? savedShowIds.has(current.tmdb_id) : false)
    : isSaved;

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="relative h-[70vh] min-h-[520px] max-h-[760px] w-full overflow-hidden select-none group"
    >
      {/* Backdrop Image */}
      {backdrop && (
        <img
          key={current.imdb_id || current.id}
          src={backdrop}
          alt={current.title}
          className="absolute inset-0 w-full h-full object-cover object-top filter brightness-[0.72] transform scale-105 transition-all duration-700 ease-out"
        />
      )}

      {/* Cinematic Vignette Gradients */}
      <div className="absolute inset-0 bg-gradient-to-t from-canvas via-canvas/60 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/45 to-transparent w-full md:w-3/4" />

      {/* Prev / Next Controls */}
      {candidates.length > 1 && (
        <>
          <button
            type="button"
            aria-label="Destaque anterior"
            onClick={() =>
              setActiveIdx((prev) => (prev - 1 + candidates.length) % candidates.length)
            }
            className="absolute left-3 top-1/2 -translate-y-1/2 z-30 p-2.5 rounded-full bg-black/55 hover:bg-black/85 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            type="button"
            aria-label="Próximo destaque"
            onClick={() => setActiveIdx((prev) => (prev + 1) % candidates.length)}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-30 p-2.5 rounded-full bg-black/55 hover:bg-black/85 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </>
      )}

      {/* Hero Content */}
      <div className="relative max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex flex-col justify-end pb-16 sm:pb-20">
        <div className="max-w-2xl space-y-4">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center gap-2.5 text-sm">
            {current.highlight_reason && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-brand-red/25 text-rose-200 font-bold text-xs border border-brand-red/40">
                <Sparkles className="w-3 h-3 text-brand-red" />
                {current.highlight_reason}
              </span>
            )}
            {current.rating > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-cinema-gold/20 text-yellow-300 font-bold border border-cinema-gold/30">
                <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                {current.rating.toFixed(1)}
              </span>
            )}
            {year && (
              <span className="inline-flex items-center gap-1 text-slate-300 font-medium">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                {year}
              </span>
            )}
            {current.status && (
              <span className="px-2 py-0.5 rounded bg-white/10 text-slate-200 text-xs font-semibold uppercase tracking-wider">
                {current.status}
              </span>
            )}
            {current.genres.slice(0, 3).map((genre) => (
              <span
                key={genre}
                className="px-2.5 py-0.5 rounded-full bg-surface-elevated/80 border border-white/10 text-slate-300 text-xs"
              >
                {genre}
              </span>
            ))}
          </div>

          {/* Title */}
          <h1 className="text-3xl sm:text-5xl md:text-6xl font-black tracking-tight text-white drop-shadow-lg leading-tight">
            {current.title}
          </h1>

          {/* Overview */}
          <p className="text-slate-300 text-sm sm:text-base line-clamp-3 leading-relaxed drop-shadow">
            {current.overview || "Sem descrição disponível."}
          </p>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => onOpenDetails(current)}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-black font-bold hover:bg-slate-200 transition-all shadow-xl hover:scale-105 active:scale-95 cursor-pointer"
            >
              <Info className="w-5 h-5 text-brand-red" />
              Ver Detalhes &amp; Episódios
            </button>

            {current.imdb_id && (
              <button
                type="button"
                onClick={() => onOpenTorrents(current)}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-red text-white font-bold hover:bg-brand-redHover transition-all shadow-cinema-glow hover:scale-105 active:scale-95 cursor-pointer"
              >
                <Download className="w-5 h-5" />
                Obter Torrents
              </button>
            )}

            <button
              type="button"
              onClick={() => onSaveToLibrary(current)}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl border transition-all cursor-pointer ${
                currentSaved
                  ? "bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-semibold"
                  : "bg-surface/80 border-white/20 text-slate-200 hover:bg-white/10"
              }`}
            >
              {currentSaved ? (
                <Check className="w-5 h-5 text-emerald-400" />
              ) : (
                <Bookmark className="w-5 h-5" />
              )}
              {currentSaved ? "Salva na Biblioteca" : "Adicionar à Minha Lista"}
            </button>
          </div>

          {/* Progress Pills */}
          {candidates.length > 1 && (
            <div className="flex items-center gap-1.5 pt-1">
              {candidates.map((item, idx) => (
                <button
                  key={`${item.imdb_id || item.id}-${idx}`}
                  type="button"
                  aria-label={`Destaque ${idx + 1}: ${item.title}`}
                  onClick={() => setActiveIdx(idx)}
                  className={`h-1.5 rounded-full transition-all cursor-pointer ${
                    idx === activeIdx ? "w-7 bg-brand-red" : "w-2 bg-white/30 hover:bg-white/60"
                  }`}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
