import React, { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { UnifiedShow } from "../types";
import { ShowCard } from "./ShowCard";

interface ShowCarouselProps {
  title: string;
  icon?: React.ReactNode;
  shows: UnifiedShow[];
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  savedShowIds?: Set<number>;
}

export const ShowCarousel: React.FC<ShowCarouselProps> = ({
  title,
  icon,
  shows,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  savedShowIds = new Set(),
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: "left" | "right") => {
    if (scrollContainerRef.current) {
      const { scrollLeft, clientWidth } = scrollContainerRef.current;
      const scrollAmount = clientWidth * 0.75;
      scrollContainerRef.current.scrollTo({
        left: direction === "left" ? scrollLeft - scrollAmount : scrollLeft + scrollAmount,
        behavior: "smooth",
      });
    }
  };

  if (!shows || shows.length === 0) {
    return null;
  }

  return (
    <div className="relative py-4 group">
      {/* Header */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{title}</h2>
          <span className="text-xs text-slate-500 font-semibold ml-2">({shows.length})</span>
        </div>
      </div>

      {/* Carousel Track with Arrow Buttons */}
      <div className="relative">
        {/* Left Arrow Button */}
        <button
          onClick={() => scroll("left")}
          className="absolute left-2 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-black/70 hover:bg-black/90 text-white backdrop-blur-md opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-xl hidden sm:flex items-center justify-center hover:scale-110 active:scale-95"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>

        {/* Scrollable Container */}
        <div
          ref={scrollContainerRef}
          className="flex gap-4 overflow-x-auto no-scrollbar scroll-smooth px-4 sm:px-6 lg:px-8 py-2"
        >
          {shows.map((show) => (
            <ShowCard
              key={`${show.source_provider}-${show.id}`}
              show={show}
              onOpenDetails={onOpenDetails}
              onOpenTorrents={onOpenTorrents}
              onSaveToLibrary={onSaveToLibrary}
              isSaved={savedShowIds.has(show.id) || (show.tmdb_id ? savedShowIds.has(show.tmdb_id) : false)}
            />
          ))}
        </div>

        {/* Right Arrow Button */}
        <button
          onClick={() => scroll("right")}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-black/70 hover:bg-black/90 text-white backdrop-blur-md opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-xl hidden sm:flex items-center justify-center hover:scale-110 active:scale-95"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
};

