import { useRef, useState } from "react";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    onFile(file);
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Upload a .knwf workflow file"
      className={`rounded border-2 border-dashed px-6 py-10 text-center transition-colors motion-reduce:transition-none
        ${isDragOver ? "border-accent bg-mist" : "border-line bg-paper"}
        ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-accent"}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
    >
      <p className="text-ink">
        Drop a <span className="font-mono text-sm">.knwf</span> file here, or click to browse
      </p>
      <p className="mt-1 text-sm text-ink/60">Up to 50MB.</p>
      <input
        ref={inputRef}
        type="file"
        accept=".knwf"
        className="hidden"
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
