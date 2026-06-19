import { useNavigate } from 'react-router-dom'
import { FileText, Trash2, Clock, CheckCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function DocumentCard({ doc, onDelete }) {
  const navigate = useNavigate()

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors group">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 bg-gray-800 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
          <FileText className="w-4 h-4 text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium truncate">{doc.filename}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-gray-500 text-xs">{formatDate(doc.created_at)}</span>
            {doc.page_count && (
              <span className="text-gray-600 text-xs">· {doc.page_count} pages</span>
            )}
          </div>

          {/* Index status */}
          <div className="flex items-center gap-1.5 mt-2">
            {doc.indexed ? (
              <>
                <CheckCircle className="w-3 h-3 text-green-500" />
                <span className="text-green-500 text-xs">Ready to query</span>
              </>
            ) : (
              <>
                <Loader2 className="w-3 h-3 text-amber-500 animate-spin" />
                <span className="text-amber-500 text-xs">Indexing...</span>
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => doc.indexed && navigate(`/document/${doc.id}`)}
            disabled={!doc.indexed}
            className={clsx(
              'text-xs px-2.5 py-1 rounded-md font-medium transition-colors',
              doc.indexed
                ? 'bg-brand-500/10 text-brand-400 hover:bg-brand-500/20'
                : 'bg-gray-800 text-gray-600 cursor-not-allowed'
            )}
          >
            Open
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(doc.id) }}
            className="p-1 text-gray-600 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}   