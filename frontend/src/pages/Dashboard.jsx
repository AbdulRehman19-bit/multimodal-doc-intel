import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSearch, LogOut, Plus } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useDocuments } from '../hooks/useDocuments'
import UploadZone from '../components/UploadZone'
import DocumentCard from '../components/DocumentCard'

export default function Dashboard() {
  const { user, signOut } = useAuth()
  const { documents, loading, uploadDocument, deleteDocument, pollIndexStatus } = useDocuments()
  const [uploading, setUploading] = useState(false)
  const navigate = useNavigate()

  const handleUpload = async (file) => {
    setUploading(true)
    try {
      const doc = await uploadDocument(file)
      if (doc) pollIndexStatus(doc.id)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-brand-500 rounded-lg flex items-center justify-center">
              <FileSearch className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-white font-semibold text-sm">DocLens</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-gray-500 text-xs">{user?.email}</span>
            <button
              onClick={signOut}
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Hero */}
        <div className="mb-8">
          <h1 className="text-white text-2xl font-semibold">Document library</h1>
          <p className="text-gray-500 text-sm mt-1">
            Upload PDFs with tables, charts, and scanned pages — ColPali reads them visually.
          </p>
        </div>

        {/* Upload */}
        <UploadZone onUpload={handleUpload} uploading={uploading} />

        {/* Documents */}
        <div className="mt-8">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600 text-sm">No documents yet. Upload one above.</p>
            </div>
          ) : (
            <div className="grid gap-3">
              <p className="text-gray-500 text-xs font-medium uppercase tracking-wider">
                {documents.length} document{documents.length !== 1 ? 's' : ''}
              </p>
              {documents.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  doc={doc}
                  onDelete={deleteDocument}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}