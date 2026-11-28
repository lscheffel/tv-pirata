import React from "react";
import {
  Search,
  Compass,
  Filter,
  Database,
  Bookmark,
  Layers,
  Settings,
  X,
} from "lucide-react";

export type AppTabId = "discover" | "catalog" | "sources" | "library" | "collections" | "config";

interface NavbarProps {
  activeTab: AppTabId;
  onTabChange: (tab: AppTabId) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  unreadCount?: number;
  systemHealth?: "healthy" | "syncing" | "degraded";
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  searchQuery,
  onSearchChange,
  unreadCount = 0,
  systemHealth = "healthy",
}) => {
  const healthDotClass =
    systemHealth === "degraded"
      ? "bg-rose-500"
      : systemHealth === "syncing"
        ? "bg-amber-400 animate-pulse"
        : "bg-emerald-400";

  const healthLabel =
    systemHealth === "degraded"
      ? "Atenção na sincronização"
      : systemHealth === "syncing"
        ? "Sincronização em andamento"
        : "Sistemas operacionais";

  return (
    <header className="fixed top-0 inset-x-0 z-40 bg-canvas/85 backdrop-blur-xl border-b border-white/10">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2 sm:gap-4">
        {/* Brand Logo */}
        <button
          type="button"
          onClick={() => {
            onTabChange("discover");
            onSearchChange("");
          }}
          className="flex items-center gap-2 cursor-pointer group shrink-0 min-h-[44px] pr-1"
        >
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-red to-rose-700 flex items-center justify-center shadow-cinema-glow transform group-hover:scale-105 transition-transform">
            <span className="text-white font-black text-lg">🏴‍☠️</span>
          </div>
          <span className="text-xl font-black tracking-tighter text-white hidden sm:block">
            TV <span className="text-brand-red">PIRATA</span>
          </span>
        </button>

        {/* Primary Desktop Tabs (5 main sections) */}
        <nav aria-label="Navegação Principal" className="hidden lg:flex items-center gap-1">
          <button
            type="button"
            onClick={() => onTabChange("discover")}
            className={`flex items-center gap-1.5 min-h-[44px] px-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === "discover"
                ? "bg-white/15 text-white shadow-inner"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            <Compass className="w-4 h-4 text-brand-red" />
            Descobrir
          </button>

          <button
            type="button"
            onClick={() => onTabChange("catalog")}
            className={`flex items-center gap-1.5 min-h-[44px] px-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === "catalog"
                ? "bg-white/15 text-white shadow-inner"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            <Filter className="w-4 h-4 text-amber-400" />
            Catálogo
          </button>

          <button
            type="button"
            onClick={() => onTabChange("sources")}
            className={`flex items-center gap-1.5 min-h-[44px] px-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === "sources"
                ? "bg-white/15 text-white shadow-inner"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            <Database className="w-4 h-4 text-emerald-400" />
            Fontes
          </button>

          <button
            type="button"
            onClick={() => onTabChange("library")}
            className={`relative flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === "library"
                ? "bg-white/15 text-white shadow-inner"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            <Bookmark className="w-4 h-4 text-sky-400" />
            Biblioteca
            {unreadCount > 0 && (
              <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-black leading-none text-white bg-brand-red rounded-full">
                {unreadCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => onTabChange("collections")}
            className={`flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === "collections"
                ? "bg-white/15 text-white shadow-inner"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            <Layers className="w-4 h-4 text-purple-400" />
            Coleções
          </button>
        </nav>

        {/* Search Input + Status/Sync/Config Button */}
        <div className="flex items-center gap-2 flex-1 max-w-md justify-end">
          <div className="relative flex-1 min-w-[140px]">
            <label htmlFor="navbar-global-search" className="sr-only">
              Buscar filmes, séries e títulos em português ou inglês
            </label>
            <Search className="w-4 h-4 text-slate-300 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              id="navbar-global-search"
              type="search"
              value={searchQuery}
              onChange={(e) => {
                onSearchChange(e.target.value);
                if (e.target.value.trim() && activeTab !== "catalog") {
                  onTabChange("catalog");
                }
              }}
              placeholder="Buscar título (PT/EN)..."
              className="w-full min-h-[44px] bg-surface-elevated border border-white/15 rounded-full pl-9 pr-11 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-brand-red focus:ring-1 focus:ring-brand-red transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                aria-label="Limpar busca global"
                title="Limpar busca"
                className="absolute right-0.5 top-1/2 -translate-y-1/2 min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Dedicated 44x44px Status, Sync & Config Button */}
          <button
            type="button"
            onClick={() => onTabChange("config")}
            aria-label={`Status, Sincronização e Configurações (${healthLabel})`}
            aria-pressed={activeTab === "config"}
            title={`Status, Sincronização & Config • ${healthLabel}`}
            className={`relative min-w-[44px] min-h-[44px] rounded-xl border flex items-center justify-center transition-all cursor-pointer shrink-0 ${
              activeTab === "config"
                ? "bg-brand-red text-white border-brand-red shadow-cinema-glow"
                : "bg-surface-elevated text-slate-200 border-white/15 hover:bg-white/10 hover:text-white"
            }`}
          >
            <Settings className="w-5 h-5" />
            <span
              className={`absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full ring-2 ring-canvas ${healthDotClass}`}
            />
          </button>
        </div>
      </div>

      {/* Compact Mobile / Tablet Navigation Bar (>=44px touch height) */}
      <nav
        aria-label="Navegação Mobile"
        className="flex lg:hidden items-center justify-around border-t border-white/10 bg-surface/95 px-2 overflow-x-auto no-scrollbar"
      >
        <button
          type="button"
          onClick={() => onTabChange("discover")}
          className={`flex items-center gap-1.5 min-h-[44px] px-3 text-xs font-bold whitespace-nowrap ${
            activeTab === "discover" ? "text-brand-red border-b-2 border-brand-red" : "text-slate-300"
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          Descobrir
        </button>

        <button
          type="button"
          onClick={() => onTabChange("catalog")}
          className={`flex items-center gap-1.5 min-h-[44px] px-3 text-xs font-bold whitespace-nowrap ${
            activeTab === "catalog" ? "text-amber-400 border-b-2 border-amber-400" : "text-slate-300"
          }`}
        >
          <Filter className="w-3.5 h-3.5" />
          Catálogo
        </button>

        <button
          type="button"
          onClick={() => onTabChange("sources")}
          className={`flex items-center gap-1.5 min-h-[44px] px-3 text-xs font-bold whitespace-nowrap ${
            activeTab === "sources"
              ? "text-emerald-400 border-b-2 border-emerald-400"
              : "text-slate-300"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Fontes
        </button>

        <button
          type="button"
          onClick={() => onTabChange("library")}
          className={`relative flex items-center gap-1.5 min-h-[44px] px-3 text-xs font-bold whitespace-nowrap ${
            activeTab === "library" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-300"
          }`}
        >
          <Bookmark className="w-3.5 h-3.5" />
          Biblioteca
          {unreadCount > 0 && (
            <span className="ml-0.5 px-1.5 py-0.5 text-[9px] font-black text-white bg-brand-red rounded-full">
              {unreadCount}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => onTabChange("collections")}
          className={`flex items-center gap-1.5 min-h-[44px] px-3 text-xs font-bold whitespace-nowrap ${
            activeTab === "collections"
              ? "text-purple-400 border-b-2 border-purple-400"
              : "text-slate-300"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Coleções
        </button>
      </nav>
    </header>
  );
};
