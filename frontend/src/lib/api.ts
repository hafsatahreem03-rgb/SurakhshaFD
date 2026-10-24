import axios, { AxiosError } from "axios";

const TOKEN_KEY = "surakshafd_token";

export const api = axios.create({ baseURL: "/api", timeout: 120000 });

/** The token lives in sessionStorage, so each browser tab has its own login. That lets institution, officer and
 *  senior approver run side by side in three tabs during a live demo. */
export const tokenStore = {
  get: () => { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { sessionStorage.setItem(TOKEN_KEY, t); } catch { /* storage blocked */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } },
};

api.interceptors.request.use((config) => {
  const t = tokenStore.get();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401 && !err.config?.url?.includes("/auth/login")) {
      tokenStore.clear();
      if (!location.pathname.startsWith("/login")) location.href = "/login?expired=1";
    }
    return Promise.reject(err);
  },
);

/** Turn any API error into a readable sentence. */
export function errorMessage(err: unknown): string {
  const e = err as AxiosError<any>;
  if (e?.code === "ECONNABORTED") return "The server took too long to respond. Please try again.";
  if (!e?.response) return "Cannot reach the SurakshaFD server. Is the backend running on port 8000?";
  const d = e.response.data?.detail;
  if (typeof d === "string") return d;
  if (d?.message) return d.unmet?.length ? `${d.message} ${d.unmet.join("; ")}.` : d.message;
  if (Array.isArray(d)) {
    return d
      .map((x: any) => `${(x.loc || []).slice(1).join(".") || "input"}: ${x.msg}`)
      .join("; ");
  }
  return `Request failed (${e.response.status}).`;
}

/** Fetch a protected file as a blob URL (documents need the auth header, so plain links won't work). */
export async function fetchBlobUrl(url: string): Promise<{ url: string; type: string }> {
  const r = await api.get(url, { responseType: "blob" });
  return { url: URL.createObjectURL(r.data), type: r.data.type };
}

export async function downloadFile(url: string, filename: string, params?: Record<string, unknown>) {
  const r = await api.get(url, { responseType: "blob", params });
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 2000);
}
