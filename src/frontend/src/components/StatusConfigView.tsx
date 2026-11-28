import React, { useCallback, useEffect, useState } from "react";
import { Settings } from "lucide-react";
import {
  ExternalSourceSummary,
  HydrationPipelineStatus,
  SchedulerTelemetry,
  SourceAdapterMetadata,
} from "../types";
import { api } from "../services/api";
import { SettingsCategoryId, SettingsSidebar } from "./settings/SettingsSidebar";
import { CatalogUpdatePanel } from "./settings/CatalogUpdatePanel";
import { SourcesProvidersPanel } from "./settings/SourcesProvidersPanel";
import { DiscoveryFeedPanel } from "./settings/DiscoveryFeedPanel";
import { ExplorePrefsPanel } from "./settings/ExplorePrefsPanel";
import { AdvancedMaintenancePanel } from "./settings/AdvancedMaintenancePanel";

interface StatusConfigViewProps {
  onHealthChange?: (health: "healthy" | "syncing" | "degraded") => void;
  onDataUpdated?: () => void;
}

export const StatusConfigView: React.FC<StatusConfigViewProps> = ({
  onHealthChange,
  onDataUpdated,
}) => {
  const [activeCategory, setActiveCategory] = useState<SettingsCategoryId>("catalog");
  const [searchQuery, setSearchQuery] = useState("");

  const [mainstreamStats, setMainstreamStats] = useState<{
    total_titles: number;
    total_episodes: number;
    hydrated_titles: number;
    eztv_badged_titles: number;
  } | null>(null);
  const [sources, setSources] = useState<ExternalSourceSummary[]>([]);
  const [adapters, setAdapters] = useState<SourceAdapterMetadata[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerTelemetry | null>(null);
  const [hydrationStatus, setHydrationStatus] = useState<HydrationPipelineStatus | null>(null);

  const loadTelemetry = useCallback(() => {
    Promise.all([
      api.explore.getMainstreamStats().catch(() => null),
      api.sources.getSummary().catch(() => null),
      api.sources.getAdapters().catch(() => null),
      api.notifications.getSchedulerStatus().catch(() => null),
      api.explore.hydration.getStatus().catch(() => null),
    ]).then(([ms, src, adp, sched, hyd]) => {
        if (ms) setMainstreamStats(ms);
        if (src) setSources(src.sources);
        if (adp) setAdapters(adp.adapters);
        if (sched) setScheduler(sched);
        if (hyd) setHydrationStatus(hyd);

        const hasDegraded = Boolean(
        src?.sources.some(
            (s) => s.enabled && (s.status === "degraded" || s.status === "challenge_required")
          )
        );
        onHealthChange?.(hasDegraded ? "degraded" : "healthy");
      });
  }, [onHealthChange]);

useEffect(() => {
  loadTelemetry();
}, [loadTelemetry]);

const degradedCount = sources.filter(
  (s) => s.enabled && (s.status === "degraded" || s.status === "challenge_required")
).length;

return (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 lg:pt-24 pb-16 space-y-6">
            {/* Compact Header */}
            <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
              <div className="flex items-center gap-2.5">
                <Settings className="w-6 h-6 text-brand-red" />
                <div>
                  <h1 className="text-2xl font-extrabold text-white tracking-tight">Configurações</h1>
                  <p className="text-xs text-slate-300">
                    Atualização do catálogo, fontes externas e preferências de navegação
                  </p>
                </div>
              </div>
            </div>

              {/* Master-Detail 2-Column Layout */}
              <div className="flex flex-col md:flex-row gap-6 items-start">
                <SettingsSidebar
                  activeCategory={activeCategory}
                  onSelectCategory={setActiveCategory}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  isHydrationRunning={hydrationStatus?.state === "RUNNING"}
                  degradedSourcesCount={degradedCount}
                />

        <main role="tabpanel" className="flex-1 min-w-0 w-full">
                    {activeCategory === "catalog" && (
            <CatalogUpdatePanel
              onRefresh={loadTelemetry}
              onHydrationStatus={setHydrationStatus}
            />
          )}

                    {activeCategory === "sources" && (
            <SourcesProvidersPanel
              sources={sources}
              adapters={adapters}
              onRefresh={loadTelemetry}
              onDataUpdated={onDataUpdated}
              onHealthChange={onHealthChange}
            />
          )}

                    {activeCategory === "discover_feed" && <DiscoveryFeedPanel />}

                    {activeCategory === "explore" && <ExplorePrefsPanel />}

                    {activeCategory === "advanced" && (
            <AdvancedMaintenancePanel
              mainstreamStats={mainstreamStats}
              scheduler={scheduler}
              onRefresh={loadTelemetry}
              onDataUpdated={onDataUpdated}
            />
          )}
          </main>
        </div>
      </div>
      );
};
