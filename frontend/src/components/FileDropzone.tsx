import { useCallback, useRef, useState } from 'react'
import { UploadCloud } from 'lucide-react'

const MAX_SIZE_BYTES = 20 * 1024 * 1024
const ACCEPTED = ['.pdf', '.png', '.jpg', '.jpeg']

export interface PickedFile {
  file: File
  error: string | null
}

export function validateFile(file: File): string | null {
  const lower = file.name.toLowerCase()
  if (!ACCEPTED.some((ext) => lower.endsWith(ext))) {
    return 'Unsupported type. Only PDF, PNG, JPG and JPEG files are allowed.'
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_SIZE_BYTES) {
    return `File is larger than the ${Math.round(MAX_SIZE_BYTES / (1024 * 1024))} MB limit.`
  }
  return null
}

export function FileDropzone({
  onFiles,
  disabled = false,
}: {
  onFiles: (files: PickedFile[]) => void
  disabled?: boolean
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || list.length === 0) return
      const picked: PickedFile[] = Array.from(list).map((file) => ({
        file,
        error: validateFile(file),
      }))
      onFiles(picked)
    },
    [onFiles],
  )

  return (
    <div
      className={`dropzone${dragging ? ' dragging' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        if (!disabled) handleFiles(event.dataTransfer.files)
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if ((event.key === 'Enter' || event.key === ' ') && !disabled) {
          event.preventDefault()
          inputRef.current?.click()
        }
      }}
      aria-label="Upload documents"
    >
      <div className="dropzone-icon">
        <UploadCloud size={26} />
      </div>
      <h3>Drop documents here</h3>
      <div className="hint">or click to choose files from your computer</div>
      <div className="limits">PDF, PNG, JPG, JPEG · up to 20 MB per file</div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED.join(',')}
        hidden
        disabled={disabled}
        onChange={(event) => {
          handleFiles(event.target.files)
          event.target.value = ''
        }}
      />
    </div>
  )
}
