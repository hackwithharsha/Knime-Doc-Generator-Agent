interface Props {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div role="alert" className="flex items-start justify-between gap-3 border border-rust/40 bg-rust/5 px-4 py-3 text-sm text-rust">
      <span>{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 underline hover:no-underline">
          Dismiss
        </button>
      )}
    </div>
  );
}
