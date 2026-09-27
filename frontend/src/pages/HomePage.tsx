import { useEffect, useState } from "react";
import { ApiError, createJob, listJobs } from "../api";
import UploadDropzone from "../components/UploadDropzone";
import JobList from "../components/JobList";
import ErrorBanner from "../components/ErrorBanner";
import type { Job } from "../types";
import { rememberFileForJob } from "../lib/retryCache";

const POLL_MS = 5000;

export default function HomePage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const data = await listJobs();
        if (!cancelled) setJobs(data);
      } catch {
        // Job history is a convenience view; a failed poll shouldn't
        // interrupt someone who's here to upload a file.
      }
    }
    refresh();
    const interval = setInterval(refresh, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handleFile(file: File) {
    setUploadError(null);
    setIsUploading(true);
    try {
      const job = await createJob(file);
      rememberFileForJob(job.id, file);
      onNavigate(`/jobs/${job.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setUploadError(err.message || "That file couldn't be read as a .knwf export. Check the file and try again.");
        } else if (err.status === 413) {
          setUploadError("That file is larger than 50MB. Export a smaller workflow, or split it into components.");
        } else {
          setUploadError("Upload failed. Check your connection and try again.");
        }
      } else {
        setUploadError("Upload failed. Check your connection and try again.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 sm:py-16">
      <h1 className="text-2xl font-semibold text-ink">KNIME Doc Generator</h1>
      <p className="mt-1 text-ink/70">
        Upload a workflow export and get reviewable documentation.
      </p>

      <div className="mt-8">
        <UploadDropzone onFile={handleFile} disabled={isUploading} />
        {uploadError && (
          <div className="mt-3">
            <ErrorBanner message={uploadError} onDismiss={() => setUploadError(null)} />
          </div>
        )}
      </div>

      <div className="mt-10">
        <h2 className="text-sm font-medium text-ink/70">Recent jobs</h2>
        <div className="mt-2">
          <JobList jobs={jobs} onSelect={(id) => onNavigate(`/jobs/${id}`)} />
        </div>
      </div>
    </main>
  );
}
