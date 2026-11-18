import React from "react";
import { Magnet } from "lucide-react";

interface MediaBadgeProps {
  compact?: boolean;
  className?: string;
  sources?: string[];
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  title?: string;
  ariaLabel?: string;
}

export const MediaBadge: React.FC<MediaBadgeProps> = ({
  compact = false,
  className = "",
  sources = [],
  onClick,
  title,
  ariaLabel,
}) => {
  const sourceLabels =
    sources.length > 0 ? sources.map((s) => s.toUpperCase()).join(", ") : "Fontes de Dados";
  const resolvedTitle = title || `Media disponível em: ${sourceLabels}`;
  const baseClass = `inline-flex items-center gap-1 rounded-md bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 text-slate-950 font-black uppercase tracking-wider shadow-[0_2px_10px_rgba(16,185,129,0.4)] border border-emerald-200/80 transition-transform ${
    compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]"
  } ${onClick ? "cursor-pointer hover:brightness-110 active:scale-95" : ""} ${className}`;

  const content = (
    <>
      <Magnet className={compact ? "w-2.5 h-2.5 shrink-0" : "w-3 h-3 shrink-0"} strokeWidth={2.5} />
      <span>Media</span>
      {sources.length > 1 && (
        <span className="px-1 rounded bg-slate-950/20 text-[8px] font-black tabular-nums">
          {sources.length}
        </span>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClick(e);
        }}
        title={resolvedTitle}
        aria-label={ariaLabel || resolvedTitle}
        className={baseClass}
      >
        {content}
      </button>
    );
  }

  return (
    <span title={resolvedTitle} className={baseClass}>
      {content}
    </span>
  );
};
