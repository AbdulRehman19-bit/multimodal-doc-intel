import { useState } from 'react'
import api from '../lib/api'
import toast from 'react-hot-toast'

export function useQuery() {
  const [messages, setMessages] = useState([])
  const [querying, setQuerying] = useState(false)

  const sendQuery = async (documentId, question) => {
    const userMessage = { role: 'user', content: question, id: Date.now() }
    setMessages((prev) => [...prev, userMessage])
    setQuerying(true)

    try {
      const { data } = await api.post('/query/', {
        document_id: documentId,
        question,
        top_k: 3,
      })

      const assistantMessage = {
        role: 'assistant',
        content: data.answer,
        retrieved_pages: data.retrieved_pages,
        langsmith_trace_url: data.langsmith_trace_url,
        id: Date.now() + 1,
      }
      setMessages((prev) => [...prev, assistantMessage])
      return data
    } catch (err) {
      const msg = err.response?.data?.detail || 'Query failed.'
      toast.error(msg)
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: msg, id: Date.now() + 1 },
      ])
    } finally {
      setQuerying(false)
    }
  }

  const clearMessages = () => setMessages([])

  return { messages, querying, sendQuery, clearMessages }
}