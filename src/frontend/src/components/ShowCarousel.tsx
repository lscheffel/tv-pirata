import React, { useMemo, useState } from "react";
import { ArrowUpRight, ChevronLeft, ChevronRight } from "lucide-react";
import { UnifiedShow } from "../types";
import { ShowCard } from "./ShowCard";

interface ShowCarouselProps {
  title: string;
  icon?: React.ReactNode;
  shows: UnifiedShow[];
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  onFilterProvider?: (provider: string) => void;
  onFilterHasMedia?: () => void;
  onOpenInCatalog?: () => void;
  savedShowIds?: Set<number>;
}

const WINDOW_SIZE = 18;
const STEP_SIZE = 6;

export const ShowCarousel: React.FC<ShowCarouselProps> = ({
  title,
  icon,
  shows,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  onFilterProvider,
  onFilterHasMedia,
  onOpenInCatalog,
  savedShowIds = new Set(),
}) => {
  const [cursor, setCursor] = useState<number>(0);

  const visibleWindow = useMemo(() => {
    if (!shows || shows.length === 0) return [];
    if (shows.length <= WINDOW_SIZE) return shows;
    const out: UnifiedShow[] = [];
    for (let i = 0; i < WINDOW_SIZE; i++) {
      out.push(shows[(cursor + i) % shows.length]);
    }
    return out;
  }, [shows, cursor]);

  if (!shows || shows.length === 0) {
    return null;
  }

  const total = shows.length;
  const startDisp = (cursor % total) + 1;
  const endDisp = Math.min(total, startDisp + Math.min(STEP_SIZE, total) - 1);

  const rotate = (dir: "left" | "right") => {
    setCursor((prev) =>
      dir === "right" ? (prev + STEP_SIZE) % total : (prev - STEP_SIZE + total) % total
    );
  };

  return (
    <div className="relative py-4 group">
      {/* Header */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{title}</h2>
          <span className="text-xs text-slate-400 font-semibold ml-1">
            ({startDisp}–{endDisp} de {total} • loop)
          </span>
        </div>

        <div className="flex items-center gap-2">
          {total > STEP_SIZE && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => rotate("left")}
                aria-label={`Anterior em ${title}`}
                className="p-1.5 rounded-lg bg-surface-elevated hover:bg-white/15 border border-white/10 text-slate-200 cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => rotate("right")}
                aria-label={`Próximo em ${title}`}
                className="p-1.5 rounded-lg bg-surface-elevated hover:bg-white/15 border border-white/10 text-slate-200 cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {onOpenInCatalog && (
            <button
              type="button"
              onClick={onOpenInCatalog}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 text-xs font-bold text-slate-200 hover:text-white transition-colors cursor-pointer"
            >
              Abrir no Catálogo
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Circular Virtualized Track */}
      <div className="relative">
        {total > STEP_SIZE && (
          <button
            type="button"
            onClick={() => rotate("left")}
            aria-label={`Rolar ${title} para esquerda`}
            className="absolute left-2 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-black/75 hover:bg-black/95 text-white backdrop-blur-md opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-xl hidden sm:flex items-center justify-center hover:scale-110 active:scale-95 cursor-pointer"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>
        )}

        <div className="flex gap-4 overflow-x-auto no-scrollbar px-4 sm:px-6 lg:px-8 py-2">
          {visibleWindow.map((show, idx) => (
            <ShowCard
              key={`${title}-${show.imdb_id || show.id}-${idx}`}
              show={show}
              onOpenDetails={onOpenDetails}
              onOpenTorrents={onOpenTorrents}
              onSaveToLibrary={onSaveToLibrary}
              onFilterProvider={onFilterProvider}
              onFilterHasMedia={onFilterHasMedia}
              isSaved={
                savedShowIds.has(show.id) ||
                (show.tmdb_id ? savedShowIds.has(show.tmdb_id) : false)
              }
            />
          ))}
        </div>

        {total > STEP_SIZE && (
          <button
            type="button"
            onClick={() => rotate("right")}
            aria-label={`Rolar ${title} para direita`}
            className="absolute right-2 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-black/75 hover:bg-black/95 text-white backdrop-blur-md opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-xl hidden sm:flex items-center justify-center hover:scale-110 active:scale-95 cursor-pointer"
          >
            <ChevronRight className="w-6 h-6" />
          </button>
        )}
      </div>
    </div>
  );
};
