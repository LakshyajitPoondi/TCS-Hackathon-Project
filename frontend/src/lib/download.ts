import { API_BASE_URL, ApiError } from "../api/client";

/** Authenticated file download (the API needs the bearer token, so a plain link cannot be used). */
export async function downloadFile(path: string, fallbackName: string) {
  const token = sessionStorage.getItem("rca_token");
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status === 404 ? "File not found." : `Download failed (${res.status}).`, res.status);
  const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") || "")?.[1] || fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
