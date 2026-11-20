import React from "react";
import { HydrationPipelineStatus } from "../../types";
import { HydrationConsoleCard } from "../HydrationConsoleCard";

interface CatalogUpdatePanelProps {
  onRefresh: () => void;
  onHydrationStatus: (status: HydrationPipelineStatus) => void;
}

export const CatalogUpdatePanel: React.FC<CatalogUpdatePanelProps> = ({
  onRefresh,
  onHydrationStatus,
}) => {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-extrabold text-white">Atualização &amp; Catálogo</h2>
        <p className="text-xs text-slate-300 mt-0.5">
          Controle único para baixar capas, sinopses em português e manter a lista de fontes
          atualizada em segundo plano.
        </p>
      </div>

      <HydrationConsoleCard
        onStepCompleted={onRefresh}
        onStatusChange={onHydrationStatus}
      />
    </div>
  );
};
