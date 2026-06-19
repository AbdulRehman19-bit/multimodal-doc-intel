import { useState, useEffect, useCallback } from 'react'
import api from '../lib/api'
import toast from 'react-hot-toast'

export function useDocuments() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true)
      const { data } = await api.get('/documents/')
      setDocuments(data.documents)
    } catch (err) {
      toast.error('Failed to load documents.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const uploadDocument = async (file) => {
    const formData = new FormData()
    formData.append('file', file)

    const toastId = toast.loading(`Uploading ${file.name}...`)
    try {
      const { data } = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setDocuments((prev) => [data, ...prev])
      toast.success('Uploaded! Indexing in background...', { id: toastId })
      return data
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed.'
      toast.error(msg, { id: toastId })
      throw err
    }
  }

  const deleteDocument = async (documentId) => {
    try {
      await api.delete(`/documents/${documentId}`)
      setDocuments((prev) => prev.filter((d) => d.id !== documentId))
      toast.success('Document deleted.')
    } catch (err) {
      toast.error('Failed to delete document.')
    }
  }

  const pollIndexStatus = async (documentId) => {
    return new Promise((resolve) => {
      const interval = setInterval(async () => {
        try {
          const { data } = await api.get(`/documents/${documentId}/index-status`)
          if (data.indexed) {
            clearInterval(interval)
            setDocuments((prev) =>
              prev.map((d) => (d.id === documentId ? { ...d, indexed: true, page_count: data.page_count } : d))
            )
            resolve(data)
          }
        } catch {
          clearInterval(interval)
          resolve(null)
        }
      }, 3000) // poll every 3 seconds
    })
  }

  return { documents, loading, uploadDocument, deleteDocument, pollIndexStatus, refetch: fetchDocuments }
}