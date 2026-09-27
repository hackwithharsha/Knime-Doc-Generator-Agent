export type JobStatus = "queued" | "parsing" | "running" | "completed" | "failed";

export interface Job {
  id: string;
  workflow_name: string | null;
  filename: string;
  status: JobStatus;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobDetail extends Job {
  markdown: string | null;
}

export type ProgressEventType =
  | "agent_started"
  | "agent_thinking"
  | "tool_used"
  | "task_completed"
  | "crew_completed"
  | "error";

export interface ProgressEvent {
  type: ProgressEventType;
  agent: string | null;
  message: string;
  created_at: string;
}

export type ExportFormat = "docx" | "pdf";
