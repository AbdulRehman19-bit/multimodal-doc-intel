import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText } from 'lucide-react'
import clsx from 'clsx'

export default function UploadZone({ onUpload, uploading }) {
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) onUpload(acceptedFiles[0])
  }, [onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: uploading,
  })

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all',
        isDragActive
          ? 'border-brand-500 bg-brand-500/5'
          : 'border-gray-700 hover:border-gray-500 bg-gray-900/50',
        uploading && 'opacity-50 cursor-not-allowed'
      )}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isDragActive ? (
          <FileText className="w-10 h-10 text-brand-500" />
        ) : (
          <Upload className="w-10 h-10 text-gray-500" />
        )}
        <div>
          <p className="text-white font-medium text-sm">
            {isDragActive ? 'Drop your PDF here' : 'Upload a PDF document'}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Drag & drop or click to browse · Max 50MB
          </p>
        </div>
      </div>
    </div>
  )
}