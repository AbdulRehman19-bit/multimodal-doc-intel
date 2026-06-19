import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, Bot, User, AlertCircle } from 'lucide-react'
import PageViewer from './PageViewer'
import TracePanel from './TracePanel'
import clsx from 'clsx'

function Message({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex items-start gap-3 justify-end">
        <div className="bg-brand-500/10 border border-brand-500/20 rounded-xl rounded-tr-sm px-4 py-2.5 max-w-lg">
          <p className="text-gray-100 text-sm">{msg.content}</p>
        </div>
        <div className="w-7 h-7 bg-gray-700 rounded-full flex items-center justify-center flex-shrink-0">
          <User className="w-3.5 h-3.5 text-gray-300" />
        </div>
      </div>
    )
  }

  if (msg.role === 'error') {
    return (
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 bg-red-500/10 rounded-full flex items-center justify-center flex-shrink-0">
          <AlertCircle className="w-3.5 h-3.5 text-red-400" />
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl rounded-tl-sm px-4 py-2.5 max-w-lg">
          <p className="text-red-400 text-sm">{msg.content}</p>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 bg-brand-500/20 rounded-full flex items-center justify-center flex-shrink-0">
        <Bot className="w-3.5 h-3.5 text-brand-400" />
      </div>
      <div className="flex-1 space-y-2 max-w-2xl">
        <div className="bg-gray-800 border border-gray-700 rounded-xl rounded-tl-sm px-4 py-3">
          <p className="text-gray-100 text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>
        {msg.retrieved_pages?.length > 0 && (
          <PageViewer pages={msg.retrieved_pages} />
        )}
        <TracePanel traceUrl={msg.langsmith_trace_url} />
      </div>
    </div>
  )
}

export default function ChatPanel({ documentId, indexed }) {
  const [input, setInput] = useState('')
  const { messages, querying, sendQuery } = require('../hooks/useQuery').useQuery()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || querying || !indexed) return
    setInput('')
    await sendQuery(documentId, q)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-16">
            <div className="w-12 h-12 bg-gray-800 rounded-xl flex items-center justify-center">
              <Bot className="w-6 h-6 text-gray-500" />
            </div>
            <div>
              <p className="text-gray-400 font-medium text-sm">Ask anything about this document</p>
              <p className="text-gray-600 text-xs mt-1">Tables, charts, and scanned pages all work</p>
            </div>
          </div>
        )}
        {messages.map((msg) => <Message key={msg.id} msg={msg} />)}
        {querying && (
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 bg-brand-500/20 rounded-full flex items-center justify-center">
              <Loader2 className="w-3.5 h-3.5 text-brand-400 animate-spin" />
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl rounded-tl-sm px-4 py-3">
              <p className="text-gray-500 text-sm">Retrieving relevant pages...</p>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-4">
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!indexed || querying}
            placeholder={indexed ? 'Ask a question...' : 'Waiting for indexing to complete...'}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || querying || !indexed}
            className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-2.5 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}