import type { DiffView, RunSummary } from "./types";

export class ApiError extends Error {
  // Declared and assigned explicitly rather than as a constructor parameter
  // property: the Vite react-ts template sets `erasableSyntaxOnly`.
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body.detail as string)
      .catch(() => response.statusText);
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function fetchRuns(): Promise<RunSummary[]> {
  const body = await getJson<{ runs: RunSummary[] }>("/api/runs");
  return body.runs;
}

export function fetchRun(runId: string, candidate?: string): Promise<DiffView> {
  const query = candidate ? `?candidate=${encodeURIComponent(candidate)}` : "";
  return getJson<DiffView>(`/api/runs/${encodeURIComponent(runId)}${query}`);
}
