import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Loader2, CheckCircle } from 'lucide-react'
import api from '../lib/api'
import { useQuery } from '../hooks/useQuery'
import ChatPanel from '../components/ChatPanel'

export default function DocumentChat() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const { messages, querying, sendQuery } = useQuery()

  useEffect(() => {
    const fetchDoc = async () => {
      try {
        const { data } = await api.get(`/documents/${id}`)
        setDoc(data)
      } catch {
        navigate('/')
      } finally {
        setLoading(false)
      }
    }
    fetchDoc()
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950">
        <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 flex-shrink-0">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="w-6 h-6 bg-gray-800 rounded-md flex items-center justify-center">
            <FileText className="w-3 h-3 text-gray-400" />
          </div>
          <span className="text-white text-sm font-medium truncate flex-1">{doc?.filename}</span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {doc?.indexed ? (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                <span className="text-green-500 text-xs">{doc.page_count} pages indexed</span>
              </>
            ) : (
              <>
                <Loader2 className="w-3.5 h-3.5 text-amber-500 animate-spin" />
                <span className="text-amber-500 text-xs">Indexing...</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Chat */}
      <div className="flex-1 overflow-hidden max-w-5xl w-full mx-auto">
        <ChatPanel
          documentId={id}
          indexed={doc?.indexed}
          messages={messages}
          querying={querying}
          sendQuery={sendQuery}
        />
      </div>
    </div>
  )
}
export default DocumentChat