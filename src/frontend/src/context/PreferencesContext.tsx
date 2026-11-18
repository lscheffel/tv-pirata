import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { UserExplorePreferences } from "../types";
import { api } from "../services/api";
import {
  DEFAULT_EXPLORE_PREFERENCES,
  loadPreferencesLocal,
  sanitizePreferences,
  savePreferencesLocal,
} from "../services/preferencesStorage";

interface PreferencesContextValue {
  preferences: UserExplorePreferences;
  syncState: "synced" | "syncing" | "local_only";
  updatePreferences: (patch: Partial<UserExplorePreferences>) => Promise<void>;
  resetPreferences: () => Promise<void>;
}

const PreferencesContext = createContext<PreferencesContextValue>({
  preferences: DEFAULT_EXPLORE_PREFERENCES,
  syncState: "local_only",
  updatePreferences: async () => {},
  resetPreferences: async () => {},
});

export const PreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [preferences, setPreferences] = useState<UserExplorePreferences>(() =>
    loadPreferencesLocal()
  );
  const [syncState, setSyncState] = useState<"synced" | "syncing" | "local_only">("local_only");

  useEffect(() => {
    let active = true;
    api.explore
      .getPreferences()
      .then((serverPrefs) => {
        if (!active) return;
        const clean = sanitizePreferences(serverPrefs);
        setPreferences(clean);
        savePreferencesLocal(clean);
        setSyncState("synced");
      })
      .catch(() => {
        if (active) setSyncState("local_only");
      });
    return () => {
      active = false;
    };
  }, []);

  const updatePreferences = useCallback(async (patch: Partial<UserExplorePreferences>) => {
    let nextMerged = DEFAULT_EXPLORE_PREFERENCES;
    setPreferences((prev) => {
      nextMerged = sanitizePreferences({ ...prev, ...patch });
      savePreferencesLocal(nextMerged);
      return nextMerged;
    });
    setSyncState("syncing");
    try {
      const saved = await api.explore.updatePreferences(nextMerged);
      const clean = sanitizePreferences(saved);
      setPreferences(clean);
      savePreferencesLocal(clean);
      setSyncState("synced");
    } catch {
      setSyncState("local_only");
    }
  }, []);

  const resetPreferences = useCallback(async () => {
    await updatePreferences(DEFAULT_EXPLORE_PREFERENCES);
  }, [updatePreferences]);

  return (
    <PreferencesContext.Provider
      value={{ preferences, syncState, updatePreferences, resetPreferences }}
    >
      {children}
    </PreferencesContext.Provider>
  );
};

export function useExplorePreferences(): PreferencesContextValue {
  return useContext(PreferencesContext);
}
