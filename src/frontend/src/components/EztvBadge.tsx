import React from "react";
import { MediaBadge } from "./MediaBadge";

interface EztvBadgeProps {
  compact?: boolean;
  className?: string;
  sources?: string[];
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  title?: string;
  ariaLabel?: string;
}

/** Backwards-compatible alias delegating to the unified MediaBadge component (ADR-012). */
export const EztvBadge: React.FC<EztvBadgeProps> = (props) => <MediaBadge {...props} />;
