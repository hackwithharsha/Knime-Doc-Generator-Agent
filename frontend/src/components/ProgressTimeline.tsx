import { AlertTriangle, CheckCircle2, CircleDot, Loader2, Send, Wrench } from "lucide-react";
import type { ProgressEvent } from "../types";

interface Props {
  events: ProgressEvent[];
}

// `isLive` is only ever true for the *last* event while the job itself is
// still mid-run: a terminal job's last stored event is always
// crew_completed/error, never agent_thinking, so "is this the last event"
// already implies "is this still actually happening" without needing the
// job's own status here. Every earlier agent_thinking event is, by
// definition, superseded — the agent has since moved on to something else —
// so its icon must stop spinning instead of implying work still in flight.
function iconFor(type: ProgressEvent["type"], isLive: boolean) {
  switch (type) {
    case "agent_started":
      return <CircleDot className="h-4 w-4 text-accent" />;
    case "agent_thinking":
      // Loader2 is a broken-ring glyph that only reads as "loading" while it
      // spins — frozen, it just looks like a rendering glitch. Only the one
      // genuinely live row gets it; every historical occurrence gets Send
      // instead, a shape that's meant to be looked at at rest and matches
      // what displayMessage() says happened ("Sent a request to Claude").
      return isLive ? (
        <Loader2 className="h-4 w-4 text-amber animate-spin motion-reduce:animate-none" />
      ) : (
        <Send className="h-4 w-4 text-amber" />
      );
    case "tool_used":
      return <Wrench className="h-4 w-4 text-amber" />;
    case "task_completed":
    case "crew_completed":
      return <CheckCircle2 className="h-4 w-4 text-moss" />;
    case "error":
      return <AlertTriangle className="h-4 w-4 text-rust" />;
  }
}

// Backend messages already read naturally as full sentences ("KNIME Workflow
// Analyst started working"), but the agent name is also shown as its own
// line above — printing both verbatim reads like a stutter. This only
// trims the display copy; the raw event data passed in is untouched.
//
// agent_thinking gets a full override rather than just the prefix trim: its
// backend message ("... is thinking...") is present-continuous, which reads
// fine for the one row that's genuinely live but is actively misleading for
// every earlier occurrence sitting permanently in this list next to a
// completed checkmark two lines down. A plain past-tense action reads
// correctly whether the row is live (paired with the spinner above) or
// history (paired with a static icon).
function displayMessage(event: ProgressEvent): string {
  if (event.type === "agent_thinking") {
    return "Sent a request to Claude";
  }
  if (event.agent && event.message.startsWith(event.agent)) {
    return event.message.slice(event.agent.length).replace(/^[\s—-]+/, "");
  }
  return event.message;
}

export default function ProgressTimeline({ events }: Props) {
  if (events.length === 0) {
    return <p className="text-sm text-ink/60">Waiting for the job to start…</p>;
  }

  return (
    <ol className="space-y-3">
      {events.map((event, i) => (
        <li key={i} className="flex items-start gap-3">
          <span className="mt-0.5 shrink-0">{iconFor(event.type, i === events.length - 1)}</span>
          <div className="min-w-0">
            {event.agent && (
              <p className="font-mono text-sm text-ink">{event.agent}</p>
            )}
            <p className={`text-sm ${event.type === "error" ? "text-rust" : "text-ink/80"}`}>
              {displayMessage(event)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
