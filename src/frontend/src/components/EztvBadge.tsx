import React from "react";

interface EztvBadgeProps {
  compact?: boolean;
  className?: string;
}

export const EztvBadge: React.FC<EztvBadgeProps> = ({ compact = false, className = "" }) => (
  <span
    title="Disponível para download imediato no catálogo EZTV"
    className={`inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 text-slate-950 font-black uppercase tracking-wider shadow-[0_0_16px_rgba(16,185,129,0.7)] ring-1 ring-white/50 ${
      compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
    } ${className}`}
  >
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={compact ? "w-3.5 h-3.5 shrink-0" : "w-4 h-4 shrink-0"}
      aria-hidden="true"
    >
      <path
        d="M8 3L12 7L16 3"
        stroke="currentColor"
        strokeWidth="2.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="3"
        y="7"
        width="18"
        height="13"
        rx="3"
        fill="currentColor"
        fillOpacity="0.18"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M13 10.2L10.3 14H12.7L11.2 17.3L14.3 13.2H11.9L13 10.2Z"
        fill="currentColor"
      />
    </svg>
    <span>EZTV</span>
  </span>
);

