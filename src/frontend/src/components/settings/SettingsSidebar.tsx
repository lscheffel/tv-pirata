import React from "react";
import {
  Compass,
  Globe,
  Search,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";

export type SettingsCategoryId = "catalog" | "sources" | "explore" | "advanced";

export interface SettingsCategoryItem {
  id: SettingsCategoryId;
  label: string;
  description: string;
  keywords: string[];
}

export const SETTINGS_CATEGORIES: SettingsCategoryItem[] = [
  {
    id: "catalog",
    label: "Atualização & Catálogo",
    description: "Capas, sinopses, velocidade e fila ao vivo",
    keywords: [
      "atualizacao",
      "catalogo",
      "capa",
      "sinopse",
      "velocidade",
      "eta",
      "progresso",
      "atividade",
      "pausar",
      "retomar",
    ],
  },
  {
    id: "sources",
    label: "Fontes & Provedores",
    description: "YTS, EZTV, TGx, Nyaa, BitSearch, Torznab",
    keywords: [
      "fonte",
      "provedor",
      "yts",
      "eztv",
      "tgx",
      "nyaa",
      "bitsearch",
      "glodls",
      "torznab",
      "cache",
      "api",
      "mirror",
      "testar",
    ],
  },
  {
    id: "explore",
    label: "Experiência no Explorar",
    description: "Selos de streaming, mídia e filtros",
    keywords: [
      "explorar",
      "selo",
      "badge",
      "streaming",
      "filtro",
      "genero",
      "preferencia",
      "clique",
    ],
  },
  {
    id: "advanced",
    label: "Avançado & Manutenção",
    description: "Agendador automático, selos cruzados e reset",
    keywords: [
      "avancado",
      "manutencao",
      "agendador",
      "scheduler",
      "biblioteca",
      "reiniciar",
      "reset",
      "banco",
      "titulo",
      "episodio",
    ],
  },
];

function normalizeSearch(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

interface SettingsSidebarProps {
  activeCategory: SettingsCategoryId;
  onSelectCategory: (id: SettingsCategoryId) => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  isHydrationRunning?: boolean;
  degradedSourcesCount?: number;
}

const ICONS: Record<SettingsCategoryId, React.ReactNode> = {
  catalog: <Sparkles className="w-4 h-4 shrink-0" />,
  sources: <Globe className="w-4 h-4 shrink-0" />,
  explore: <Compass className="w-4 h-4 shrink-0" />,
  advanced: <Wrench className="w-4 h-4 shrink-0" />,
};

export const SettingsSidebar: React.FC<SettingsSidebarProps> = ({
  activeCategory,
  onSelectCategory,
  searchQuery,
  onSearchChange,
  isHydrationRunning = false,
  degradedSourcesCount = 0,
}) => {
  const normQ = normalizeSearch(searchQuery);
  const filtered = SETTINGS_CATEGORIES.filter((cat) => {
    if (!normQ) return true;
    return (
      normalizeSearch(cat.label).includes(normQ) ||
      normalizeSearch(cat.description).includes(normQ) ||
      cat.keywords.some((k) => k.includes(normQ))
    );
  });

  return (
    <aside className="w-full md:w-64 shrink-0 space-y-3">
      {/* Quick Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => {
            const val = e.target.value;
            onSearchChange(val);
            const n = normalizeSearch(val);
            if (n) {
              const firstHit = SETTINGS_CATEGORIES.find(
                (cat) =>
                  normalizeSearch(cat.label).includes(n) ||
                  cat.keywords.some((k) => k.includes(n))
              );
              if (firstHit && firstHit.id !== activeCategory) {
                onSelectCategory(firstHit.id);
              }
            }
          }}
          placeholder="Filtrar ajustes..."
          aria-label="Filtrar ajustes"
          className="w-full min-h-[44px] bg-surface-elevated border border-white/15 rounded-xl pl-9 pr-9 text-xs font-medium text-white placeholder:text-slate-400 focus:outline-none focus:border-cyan-400"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            aria-label="Limpar filtro"
            className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Category Navigation */}
      <nav
        role="tablist"
        aria-label="Categorias de configurações"
        className="flex md:flex-col gap-1.5 overflow-x-auto pb-1 md:pb-0"
      >
        {filtered.length === 0 ? (
          <div className="p-3 rounded-xl bg-surface-elevated border border-white/10 text-xs text-slate-400">
            Nenhuma categoria corresponde a &ldquo;{searchQuery}&rdquo;.
          </div>
        ) : (
          filtered.map((cat) => {
            const selected = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => onSelectCategory(cat.id)}
                className={`min-h-[44px] shrink-0 md:w-full text-left px-3 py-2.5 rounded-xl border transition-all cursor-pointer flex items-start gap-2.5 ${
                  selected
                    ? "bg-cyan-500/15 border-cyan-400/50 text-white shadow-sm"
                    : "bg-surface-elevated/60 border-white/10 text-slate-300 hover:bg-surface-elevated hover:text-white"
                }`}
              >
                <span className={`mt-0.5 ${selected ? "text-cyan-300" : "text-slate-400"}`}>
                  {ICONS[cat.id]}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold truncate">{cat.label}</span>
                    {cat.id === "catalog" && isHydrationRunning && (
                      <span
                        title="Atualização em andamento"
                        className="w-2 h-2 rounded-full bg-cyan-400 animate-ping shrink-0"
                      />
                    )}
                    {cat.id === "sources" && degradedSourcesCount > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-200 border border-amber-400/30">
                        {degradedSourcesCount}
                      </span>
                    )}
                  </div>
                  <p className="hidden md:block text-[11px] text-slate-400 truncate mt-0.5">
                    {cat.description}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </nav>
    </aside>
  );
};
