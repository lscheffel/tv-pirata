import React, { useState } from "react";
import { Star, Download, Bookmark, Check, Film } from "lucide-react";
import { UnifiedShow } from "../types";

interface ShowCardProps {
  show: UnifiedShow;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  isSaved?: boolean;
}

export const ShowCard: React.FC<ShowCardProps> = ({
  show,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  isSaved = false,
}) => {
  const [imageError, setImageError] = useState(false);
  const year = show.first_air_date ? new Date(show.first_air_date).getFullYear() : "";

  return (
    <div
      onClick={() => onOpenDetails(show)}
      className="group relative flex-none w-[160px] sm:w-[190px] md:w-[220px] cursor-pointer select-none rounded-xl overflow-hidden bg-surface transition-all duration-300 hover:scale-105 hover:z-20 hover:shadow-card-elevation"
    >
      {/* Poster Image Container */}
      <div className="relative aspect-[2/3] w-full bg-surface-elevated overflow-hidden">
        {show.poster_url && !imageError ? (
          <img
            src={show.poster_url}
            alt={show.title}
            loading="lazy"
            onError={() => setImageError(true)}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center bg-gradient-to-br from-surface-elevated to-surface">
            <Film className="w-10 h-10 text-slate-600 mb-2" />
            <span className="text-xs text-slate-400 font-semibold line-clamp-2">{show.title}</span>
          </div>
        )}

        {/* Rating Badge */}
        {show.rating > 0 && (
          <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/75 backdrop-blur-md text-yellow-400 text-xs font-bold border border-yellow-500/20">
            <Star className="w-3 h-3 fill-yellow-400" />
            {show.rating.toFixed(1)}
          </div>
        )}

        {/* Gradient Shadow Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-canvas via-transparent to-transparent opacity-80 group-hover:opacity-90 transition-opacity" />

        {/* Hover Action Overlay */}
        <div className="absolute inset-x-0 bottom-0 p-3 flex flex-col justify-end transform translate-y-2 group-hover:translate-y-0 transition-transform">
          <h3 className="text-sm font-bold text-white line-clamp-1 group-hover:text-brand-red transition-colors">
            {show.title}
          </h3>

          <div className="flex items-center justify-between mt-1 text-xs text-slate-400">
            <span>{year || "Série"}</span>
            <span className="text-slate-500 uppercase text-[10px] tracking-wider font-semibold">
              {show.source_provider}
            </span>
          </div>

          {/* Quick Action Buttons (Show on hover) */}
          <div className="flex items-center gap-1.5 mt-2.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            {show.imdb_id && (
              <button
                title="Ver Torrents EZTV"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenTorrents(show);
                }}
                className="p-1.5 rounded-lg bg-brand-red hover:bg-brand-redHover text-white transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
            )}

            {onSaveToLibrary && (
              <button
                title={isSaved ? "Salva na Biblioteca" : "Adicionar à Lista"}
                onClick={(e) => {
                  e.stopPropagation();
                  onSaveToLibrary(show);
                }}
                className={`p-1.5 rounded-lg border transition-colors ${
                  isSaved
                    ? "bg-emerald-900/80 border-emerald-500 text-emerald-300"
                    : "bg-surface-elevated/80 border-white/20 text-slate-300 hover:text-white hover:bg-white/10"
                }`}
              >
                {isSaved ? <Check className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

