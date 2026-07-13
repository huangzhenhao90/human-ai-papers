"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { preload } from "react-dom";
import { usePathname } from "next/navigation";
import {
  getCatalogSnapshot,
  loadCatalog,
  resetCatalogCache,
  type CatalogData,
} from "@/lib/data";

type PapersDataContextValue = CatalogData & {
  loading: boolean;
  error: Error | null;
  reload: () => void;
};

const PapersDataContext = createContext<PapersDataContextValue | null>(null);
const CATALOG_PATHS = ["/data/papers.json", "/data/meta.json", "/data/updates.json"] as const;

function isExplorerPath(pathname: string) {
  return pathname === "/" || pathname === "/recent" || pathname === "/favorites";
}

export function PapersDataProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const shouldLoad = isExplorerPath(pathname);
  const [data, setData] = useState<CatalogData | null>(() => getCatalogSnapshot());
  const [error, setError] = useState<Error | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  if (shouldLoad && !data && !error) {
    for (const path of CATALOG_PATHS) {
      preload(path, { as: "fetch", crossOrigin: "anonymous" });
    }
  }

  useEffect(() => {
    if (!shouldLoad || data) return;
    let active = true;
    setError(null);
    loadCatalog()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((reason) => {
        if (!active) return;
        setError(reason instanceof Error ? reason : new Error(String(reason)));
      });
    return () => {
      active = false;
    };
  }, [data, reloadKey, shouldLoad]);

  const reload = useCallback(() => {
    resetCatalogCache();
    setData(null);
    setError(null);
    setReloadKey((key) => key + 1);
  }, []);

  const value = useMemo<PapersDataContextValue>(() => ({
    papers: data?.papers || [],
    meta: data?.meta || null,
    updates: data?.updates || null,
    demo: data?.demo || false,
    loading: shouldLoad && !data && !error,
    error,
    reload,
  }), [data, error, reload, shouldLoad]);

  return <PapersDataContext.Provider value={value}>{children}</PapersDataContext.Provider>;
}

export function usePapersData() {
  const value = useContext(PapersDataContext);
  if (!value) throw new Error("usePapersData must be used within PapersDataProvider");
  return value;
}
