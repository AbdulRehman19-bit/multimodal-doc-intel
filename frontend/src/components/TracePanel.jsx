import { ExternalLink, Activity } from 'lucide-react'

export default function TracePanel({ traceUrl }) {
  if (!traceUrl) return null
  return (
    <a
      href={traceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand-400 transition-colors mt-1"
    >
      <Activity className="w-3 h-3" />
      View LangSmith trace
      <ExternalLink className="w-3 h-3" />
    </a>
  )
}