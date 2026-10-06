import { request } from "./client";
import type {
  AnalysisResponse,
  EvalsResponse,
  IncidentRef,
  IncidentSummary,
  SaveCaseRequest,
  SaveCaseResponse,
  SignalsResponse,
  Sop,
} from "../types/api";

const enc = encodeURIComponent;
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const health = () => request<{ status: string }>("/health");
export const listIncidents = () => request<IncidentRef[]>("/api/incidents");
export const getIncident = (id: string) => request<IncidentSummary>(`/api/incidents/${enc(id)}`);
export const getSignals = (id: string) => request<SignalsResponse>(`/api/incidents/${enc(id)}/signals`);
export const analyzeIncident = (id: string) =>
  request<AnalysisResponse>(`/api/incidents/${enc(id)}/analyze`, { method: "POST" });

export function uploadIncident(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<IncidentRef>("/api/incidents/upload", { method: "POST", body: form });
}

export const saveCase = (body: SaveCaseRequest) => request<SaveCaseResponse>("/api/cases", json(body));
export const getSop = (id: string) => request<Sop>(`/api/sops/${enc(id)}`);
export const getEvals = () => request<EvalsResponse>("/api/evals");
