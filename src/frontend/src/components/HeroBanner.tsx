import React from "react";
import { Info, Download, Star, Calendar, Bookmark, Check } from "lucide-react";
import { UnifiedShow } from "../types";

interface HeroBannerProps {
  show: UnifiedShow | null;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary: (show: UnifiedShow) => void;
  isSaved?: boolean;
}

export const HeroBanner: React.FC<HeroBannerProps> = ({
  show,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  isSaved = false,
}) => {
  if (!show) {
    return (
      <div className="relative h-[65vh] min-h-[480px] max-h-[720px] w-full bg-surface-elevated animate-pulse flex items-center justify-center">
        <span className="text-slate-500 font-medium">Carregando catálogo cinematográfico...</span>
      </div>
    );
  }

  const backdrop = show.backdrop_url || show.poster_url || "";
  const year = show.first_air_date ? new Date(show.first_air_date).getFullYear() : "";

  return (
    <div className="relative h-[70vh] min-h-[520px] max-h-[760px] w-full overflow-hidden select-none">
      {/* Backdrop Image */}
      {backdrop && (
        <img
          src={backdrop}
          alt={show.title}
          className="absolute inset-0 w-full h-full object-cover object-top filter brightness-[0.7] transform scale-105 transition-transform duration-1000 ease-out"
        />
      )}

      {/* Cinematic Vignette Gradients */}
      <div className="absolute inset-0 bg-gradient-to-t from-canvas via-canvas/60 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/40 to-transparent w-full md:w-3/4" />

      {/* Hero Content */}
      <div className="relative max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex flex-col justify-end pb-16 sm:pb-20">
        <div className="max-w-2xl space-y-4">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {show.rating > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-cinema-gold/20 text-yellow-300 font-bold border border-cinema-gold/30">
                <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                {show.rating.toFixed(1)}
              </span>
            )}
            {year && (
              <span className="inline-flex items-center gap-1 text-slate-300 font-medium">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                {year}
              </span>
            )}
            {show.status && (
              <span className="px-2 py-0.5 rounded bg-white/10 text-slate-200 text-xs font-semibold uppercase tracking-wider">
                {show.status}
              </span>
            )}
            {show.genres.slice(0, 3).map((genre) => (
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
            {show.title}
          </h1>

          {/* Overview */}
          <p className="text-slate-300 text-sm sm:text-base line-clamp-3 leading-relaxed drop-shadow">
            {show.overview || "Sem descrição disponível."}
          </p>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              onClick={() => onOpenDetails(show)}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-black font-bold hover:bg-slate-200 transition-all shadow-xl hover:scale-105 active:scale-95"
            >
              <Info className="w-5 h-5 text-brand-red" />
              Ver Detalhes & Episódios
            </button>

            {show.imdb_id && (
              <button
                onClick={() => onOpenTorrents(show)}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-red text-white font-bold hover:bg-brand-redHover transition-all shadow-cinema-glow hover:scale-105 active:scale-95"
              >
                <Download className="w-5 h-5" />
                Obter Torrents
              </button>
            )}

            <button
              onClick={() => onSaveToLibrary(show)}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl border transition-all ${
                isSaved
                  ? "bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-semibold"
                  : "bg-surface/80 border-white/20 text-slate-200 hover:bg-white/10"
              }`}
            >
              {isSaved ? <Check className="w-5 h-5 text-emerald-400" /> : <Bookmark className="w-5 h-5" />}
              {isSaved ? "Salva na Biblioteca" : "Adicionar à Minha Lista"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

