import type { JobStatus } from "../types";

const LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  parsing: "Parsing",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

const DOT_CLASSES: Record<JobStatus, string> = {
  queued: "bg-slate-400",
  parsing: "bg-amber",
  running: "bg-amber",
  completed: "bg-moss",
  failed: "bg-rust",
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const isActive = status === "parsing" || status === "running";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-ink">
      <span
        className={`h-2 w-2 rounded-full ${DOT_CLASSES[status]} ${
          isActive ? "animate-pulse motion-reduce:animate-none" : ""
        }`}
        aria-hidden="true"
      />
      {LABELS[status]}
    </span>
  );
}
