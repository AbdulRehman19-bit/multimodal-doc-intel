import { X } from 'lucide-react'

export default function PageViewer({ pages, onClose }) {
  if (!pages || pages.length === 0) return null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <p className="text-gray-400 text-xs font-medium">Retrieved pages</p>
        {onClose && (
          <button onClick={onClose} className="text-gray-600 hover:text-gray-400">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      <div className="flex gap-3 p-3 overflow-x-auto">
        {pages.map((page) => (
          <div key={page.page_number} className="flex-shrink-0">
            <img
              src={page.image_url}
              alt={`Page ${page.page_number}`}
              className="h-48 w-auto rounded-lg border border-gray-700 object-contain bg-gray-950"
            />
            <div className="mt-1.5 text-center">
              <span className="text-gray-500 text-xs">Page {page.page_number}</span>
              <span className="text-gray-600 text-xs ml-1">
                · {(page.relevance_score * 100).toFixed(0)}% match
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}