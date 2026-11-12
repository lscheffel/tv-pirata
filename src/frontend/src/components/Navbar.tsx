import React, { useState, useEffect } from "react";
import { Search, Film, Bookmark, Layers, X, Menu, Zap } from "lucide-react";

interface NavbarProps {
  activeTab: "discover" | "catalog" | "library" | "collections";
  onTabChange: (tab: "discover" | "catalog" | "library" | "collections") => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  unreadCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  searchQuery,
  onSearchChange,
  unreadCount = 0,
}) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 40);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        isScrolled
          ? "bg-canvas/90 backdrop-blur-md border-b border-white/5 py-3 shadow-2xl"
          : "bg-gradient-to-b from-black/80 via-black/40 to-transparent py-5"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
        {/* Logo & Brand */}
        <div className="flex items-center gap-8">
          <div
            onClick={() => onTabChange("discover")}
            className="flex items-center gap-2 cursor-pointer group"
          >
            <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
              <span className="text-brand-red group-hover:scale-105 transition-transform">TV</span>
              <span className="text-white">PIRATA</span>
              <span className="text-xl">🏴‍☠️</span>
            </span>
          </div>

          {/* Desktop Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-1">
            <button
              onClick={() => onTabChange("discover")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "discover"
                  ? "bg-white/10 text-white shadow-inner font-semibold"
                  : "text-slate-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Film className="w-4 h-4 text-brand-red" />
              Descobrir
            </button>
            <button
              onClick={() => onTabChange("catalog")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "catalog"
                  ? "bg-white/10 text-white shadow-inner font-semibold"
                  : "text-slate-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Zap className="w-4 h-4 text-yellow-400" />
              Catálogo EZTV
            </button>
            <button
              onClick={() => onTabChange("library")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "library"
                  ? "bg-white/10 text-white shadow-inner font-semibold"
                  : "text-slate-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Bookmark className="w-4 h-4 text-brand-red" />
              <span>Minha Biblioteca</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-black bg-brand-red text-white shadow-cinema-glow animate-pulse">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => onTabChange("collections")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "collections"
                  ? "bg-white/10 text-white shadow-inner font-semibold"
                  : "text-slate-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Layers className="w-4 h-4 text-brand-red" />
              Coleções & Tags
            </button>
          </nav>
        </div>

        {/* Search Bar & Mobile Menu Toggle */}
        <div className="flex items-center gap-3">
          <div
            className={`relative flex items-center rounded-full transition-all duration-300 border ${
              searchFocused
                ? "w-48 sm:w-72 bg-surface-elevated/90 border-brand-red shadow-cinema-glow"
                : "w-36 sm:w-60 bg-surface/70 border-white/10"
            }`}
          >
            <Search className="w-4 h-4 text-slate-400 ml-3 shrink-0" />
            <input
              type="text"
              placeholder="Buscar séries..."
              value={searchQuery}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full bg-transparent py-2 pl-2 pr-8 text-sm text-white placeholder-slate-400 focus:outline-none"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange("")}
                className="absolute right-2 text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-slate-300 hover:text-white rounded-lg hover:bg-white/10"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-canvas/95 backdrop-blur-xl border-b border-white/10 px-4 pt-3 pb-4 space-y-2">
          <button
            onClick={() => {
              onTabChange("discover");
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${
              activeTab === "discover" ? "bg-brand-red/20 text-white font-semibold" : "text-slate-300"
            }`}
          >
            <Film className="w-5 h-5 text-brand-red" />
            Descobrir
          </button>
          <button
            onClick={() => {
              onTabChange("catalog");
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${
              activeTab === "catalog" ? "bg-brand-red/20 text-white font-semibold" : "text-slate-300"
            }`}
          >
            <Zap className="w-5 h-5 text-yellow-400" />
            Catálogo EZTV
          </button>
          <button
            onClick={() => {
              onTabChange("library");
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${
              activeTab === "library" ? "bg-brand-red/20 text-white font-semibold" : "text-slate-300"
            }`}
          >
            <Bookmark className="w-5 h-5 text-brand-red" />
            <span className="flex-1 text-left">Minha Biblioteca</span>
            {unreadCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-black bg-brand-red text-white shadow-cinema-glow">
                {unreadCount}
              </span>
            )}
          </button>
          <button
            onClick={() => {
              onTabChange("collections");
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${
              activeTab === "collections" ? "bg-brand-red/20 text-white font-semibold" : "text-slate-300"
            }`}
          >
            <Layers className="w-5 h-5 text-brand-red" />
            Coleções & Tags
          </button>
        </div>
      )}
    </header>
  );
};

