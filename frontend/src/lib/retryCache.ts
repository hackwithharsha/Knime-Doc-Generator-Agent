/**
 * The backend has no "retry" endpoint — a job is a one-shot record of a past
 * upload, and re-running one means submitting the file again as a new job.
 * There's nowhere durable to keep the original bytes (uploads live in a
 * server-side volume, not addressable by the client), so this in-memory map
 * only helps within the same browser session/tab: if the user is still on
 * the tab that uploaded the file, "Retry" can resubmit it directly. If they
 * arrived at the job page some other way (e.g. a bookmarked link, a reload),
 * the map is empty and the UI falls back to "Upload a new file" instead.
 */
const filesByJobId = new Map<string, File>();

export function rememberFileForJob(jobId: string, file: File): void {
  filesByJobId.set(jobId, file);
}

export function getRememberedFile(jobId: string): File | undefined {
  return filesByJobId.get(jobId);
}
