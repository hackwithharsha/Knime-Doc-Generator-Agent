import axios, { AxiosError } from "axios";
import type { ExportFormat, Job, JobDetail, ProgressEvent } from "./types";

/**
 * All calls are relative (`/api/...`). In dev, Vite's own proxy (vite.config.ts)
 * forwards them server-side to the `api` container over the Docker network, so
 * the browser only ever talks to one origin — no CORS, no env var to keep in sync.
 */
const client = axios.create({ baseURL: "/api" });

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function unwrap(err: unknown): never {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    throw new ApiError(
      typeof detail === "string" ? detail : err.message,
      err.response?.status ?? 0
    );
  }
  throw err;
}

export async function createJob(file: File): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await client.post<Job>("/doc/jobs", form);
    return data;
  } catch (err) {
    unwrap(err);
  }
}

export async function listJobs(): Promise<Job[]> {
  try {
    const { data } = await client.get<Job[]>("/doc/jobs");
    return data;
  } catch (err) {
    unwrap(err);
  }
}

export async function getJob(id: string): Promise<JobDetail> {
  try {
    const { data } = await client.get<JobDetail>(`/doc/jobs/${id}`);
    return data;
  } catch (err) {
    unwrap(err);
  }
}

export function exportHref(id: string, format: ExportFormat): string {
  return `/api/doc/jobs/${id}/export?format=${format}`;
}

const TERMINAL_EVENT_TYPES = new Set(["crew_completed", "error"]);

/** Subscribes to the SSE progress stream. Returns an unsubscribe function. */
export function subscribeToEvents(
  id: string,
  onEvent: (event: ProgressEvent) => void
): () => void {
  const source = new EventSource(`/api/doc/jobs/${id}/events`);

  source.onmessage = (msg) => {
    const event = JSON.parse(msg.data) as ProgressEvent;
    onEvent(event);
    if (TERMINAL_EVENT_TYPES.has(event.type)) {
      source.close();
    }
  };

  // A dropped connection before a terminal event fires (network blip, server
  // restart) — the caller re-fetches job status via getJob() as the source of
  // truth rather than this stream trying to reconnect and re-replay itself.
  source.onerror = () => {
    source.close();
  };

  return () => source.close();
}
