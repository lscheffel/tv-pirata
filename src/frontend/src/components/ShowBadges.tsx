import React from "react";
import { CheckCircle2, Clock, Radio, Sparkles, Tv, XCircle } from "lucide-react";

interface StatusBadgeProps {
  status?: string | null;
  compact?: boolean;
}

const STATUS_STYLE_MAP: Array<{
  keys: string[];
  label: string;
  classes: string;
  dotColor?: string;
  icon: "live" | "ended" | "tbd" | "dev" | "canceled";
}> = [
  {
    keys: ["running", "returning series", "airing", "in production"],
    label: "Em Exibição",
    classes: "bg-emerald-950/90 text-emerald-300 border-emerald-500/45",
    dotColor: "bg-emerald-400",
    icon: "live",
  },
  {
    keys: ["ended", "completed"],
    label: "Finalizada",
    classes: "bg-slate-900/90 text-slate-300 border-slate-500/40",
    icon: "ended",
  },
  {
    keys: ["to be determined", "tbd"],
    label: "A Definir",
    classes: "bg-amber-950/90 text-amber-300 border-amber-500/45",
    icon: "tbd",
  },
  {
    keys: ["in development", "planned", "pilot"],
    label: "Em Produção",
    classes: "bg-purple-950/90 text-purple-300 border-purple-500/45",
    icon: "dev",
  },
  {
    keys: ["canceled", "cancelled"],
    label: "Cancelada",
    classes: "bg-rose-950/90 text-rose-300 border-rose-500/45",
    icon: "canceled",
  },
];

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, compact = false }) => {
  if (!status || status.toLowerCase() === "unknown") return null;

  const norm = status.trim().toLowerCase();
  const matched = STATUS_STYLE_MAP.find((entry) =>
    entry.keys.some((k) => norm === k || norm.includes(k))
  );

  const label = matched ? matched.label : status;
  const classes = matched
    ? matched.classes
    : "bg-slate-900/90 text-slate-200 border-white/20";

  const iconSize = compact ? "w-2.5 h-2.5" : "w-3 h-3";

  return (
    <span
      title={`Status da série: ${status}`}
      className={`inline-flex items-center gap-1 rounded-md border backdrop-blur-md font-bold uppercase tracking-wide ${classes} ${
        compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]"
      }`}
    >
      {matched?.icon === "live" && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
        </span>
      )}
      {matched?.icon === "ended" && <CheckCircle2 className={iconSize} />}
      {matched?.icon === "tbd" && <Clock className={iconSize} />}
      {matched?.icon === "dev" && <Sparkles className={iconSize} />}
      {matched?.icon === "canceled" && <XCircle className={iconSize} />}
      {!matched && <Radio className={iconSize} />}
      <span className="truncate max-w-[92px]">{label}</span>
    </span>
  );
};

interface ProviderBadgeProps {
  provider?: string | null;
  compact?: boolean;
}

function getProviderStyle(provider: string): string {
  const p = provider.toLowerCase();
  if (p.includes("netflix")) return "bg-red-950/90 text-red-300 border-red-500/45";
  if (p.includes("prime") || p.includes("amazon"))
    return "bg-sky-950/90 text-sky-300 border-sky-500/45";
  if (p.includes("paramount")) return "bg-indigo-950/90 text-indigo-300 border-indigo-500/45";
  if (p.includes("apple")) return "bg-zinc-900/95 text-zinc-100 border-zinc-400/45";
  if (p.includes("max") || p.includes("hbo"))
    return "bg-violet-950/90 text-violet-300 border-violet-500/45";
  if (p.includes("disney")) return "bg-blue-950/90 text-blue-300 border-blue-500/45";
  if (p.includes("hulu")) return "bg-emerald-950/90 text-emerald-300 border-emerald-500/45";
  return "bg-cyan-950/90 text-cyan-300 border-cyan-500/40";
}

export const ProviderBadge: React.FC<ProviderBadgeProps> = ({ provider, compact = false }) => {
  if (!provider) return null;
  const style = getProviderStyle(provider);

  return (
    <span
      title={`Serviço / Rede: ${provider}`}
      className={`inline-flex items-center gap-1 rounded-md border backdrop-blur-md font-bold tracking-wide ${style} ${
        compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]"
      }`}
    >
      <Tv className={compact ? "w-2.5 h-2.5 shrink-0" : "w-3 h-3 shrink-0"} />
      <span className="truncate max-w-[96px]">{provider}</span>
    </span>
  );
};

