import type { Job } from "../types";
import { relativeTime } from "../lib/format";
import StatusBadge from "./StatusBadge";

interface Props {
  jobs: Job[];
  onSelect: (id: string) => void;
}

export default function JobList({ jobs, onSelect }: Props) {
  if (jobs.length === 0) {
    return (
      <p className="text-sm text-ink/60">
        No jobs yet. Upload a .knwf file above to generate its first doc.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line border-t border-b border-line">
      {jobs.map((job) => (
        <li key={job.id}>
          <button
            onClick={() => onSelect(job.id)}
            className="flex w-full items-center justify-between gap-4 px-1 py-3 text-left hover:bg-mist"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate font-mono text-sm text-ink">
                {job.workflow_name ?? job.filename}
              </span>
            </span>
            <StatusBadge status={job.status} />
            <span className="w-16 shrink-0 text-right text-sm text-ink/60">
              {relativeTime(job.created_at)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
