import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";

/** Small data-loading hook: GET `url` (re-runs when url/params change) with loading + error state. */
export function useFetch<T>(url: string | null, params?: Record<string, unknown>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(params || {});

  const load = useCallback(async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    try {
      const clean = Object.fromEntries(Object.entries(params || {}).filter(([, v]) => v !== "" && v != null));
      const r = await api.get<T>(url, { params: clean });
      setData(r.data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, key]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load, setData };
}
