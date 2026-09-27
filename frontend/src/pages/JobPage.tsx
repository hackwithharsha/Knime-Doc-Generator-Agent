import { ArrowLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, createJob, getJob, subscribeToEvents } from "../api";
import ProgressTimeline from "../components/ProgressTimeline";
import StatusBadge from "../components/StatusBadge";
import ErrorBanner from "../components/ErrorBanner";
import DocView from "../components/DocView";
import type { JobDetail, ProgressEvent } from "../types";
import { getRememberedFile, rememberFileForJob } from "../lib/retryCache";

interface Props {
  jobId: string;
  onNavigate: (path: string) => void;
}

export default function JobPage({ jobId, onNavigate }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const jobIdRef = useRef(jobId);
  jobIdRef.current = jobId;

  useEffect(() => {
    let cancelled = false;
    setJob(null);
    setEvents([]);
    setLoadError(null);

    async function refreshJob(): Promise<JobDetail | null> {
      try {
        const data = await getJob(jobIdRef.current);
        if (!cancelled) setJob(data);
        return data;
      } catch (err) {
        if (cancelled) return null;
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "This job doesn't exist, or has been removed."
            : "Couldn't load this job. Check your connection and reload the page."
        );
        return null;
      }
    }

    // The worker's crew_completed/error progress events fire mid-pipeline —
    // before the final DocDocument row is written and the job's own status
    // is set to completed/failed (see doc_pipeline.py: run_doc_crew()
    // returns, *then* the document is saved, *then* the status is set).
    // A single refetch right on that event can land in that gap and show a
    // stale "running" pill forever, since the SSE stream has already closed
    // by then. Poll briefly until the job itself reports a terminal status.
    async function waitForTerminalStatus() {
      for (let attempt = 0; attempt < 25; attempt++) {
        const data = await refreshJob();
        if (cancelled || !data) return;
        if (data.status === "completed" || data.status === "failed") return;
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
    }

    refreshJob();

    const unsubscribe = subscribeToEvents(jobId, (event) => {
      if (cancelled) return;
      setEvents((prev) => [...prev, event]);
      if (event.type === "crew_completed" || event.type === "error") {
        waitForTerminalStatus();
      } else {
        refreshJob();
      }
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [jobId]);

  async function handleRetry() {
    const file = getRememberedFile(jobId);
    if (!file) {
      onNavigate("/");
      return;
    }
    setIsRetrying(true);
    try {
      const newJob = await createJob(file);
      rememberFileForJob(newJob.id, file);
      onNavigate(`/jobs/${newJob.id}`);
    } catch {
      setLoadError("Retry failed. Check your connection and try again, or upload the file again from the home page.");
    } finally {
      setIsRetrying(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-16">
      <button
        onClick={() => onNavigate("/")}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-ink/70 hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to jobs
      </button>

      {loadError && (
        <ErrorBanner message={loadError} />
      )}

      {!loadError && !job && <p className="text-sm text-ink/60">Loading…</p>}

      {job && (
        <>
          <div className="mb-8 flex items-center justify-between gap-4">
            <h1 className="min-w-0 truncate text-xl font-semibold text-ink">
              {job.workflow_name ?? job.filename}
            </h1>
            <StatusBadge status={job.status} />
          </div>

          {job.status === "failed" && (
            <div className="mb-8">
              <ErrorBanner
                message={job.error ?? "The job failed for an unknown reason."}
              />
              <button
                onClick={handleRetry}
                disabled={isRetrying}
                className="mt-3 border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent hover:text-white disabled:opacity-60"
              >
                {getRememberedFile(jobId)
                  ? isRetrying
                    ? "Retrying…"
                    : "Retry with the same file"
                  : "Upload a new file"}
              </button>
            </div>
          )}

          {job.status === "completed" && job.markdown ? (
            <>
              <DocView
                jobId={job.id}
                workflowName={job.workflow_name ?? job.filename}
                generatedAt={job.updated_at}
                markdown={job.markdown}
              />
              <details className="mt-6 border border-line bg-mist/40 px-4 py-3">
                <summary className="cursor-pointer text-sm font-medium text-ink/70">
                  Agent activity ({events.length} steps)
                </summary>
                <div className="mt-4">
                  <ProgressTimeline events={events} />
                </div>
              </details>
            </>
          ) : (
            job.status !== "failed" && (
              <section>
                <h2 className="mb-3 text-sm font-medium text-ink/70">Progress</h2>
                <ProgressTimeline events={events} />
              </section>
            )
          )}
        </>
      )}
    </main>
  );
}
