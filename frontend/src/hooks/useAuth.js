import { useEffect } from 'react'
import { useAuthStore } from '../store/authStore'

export function useAuth() {
  const { user, session, loading, initialize, signOut } = useAuthStore()

  useEffect(() => {
    initialize()
  }, [])

  return { user, session, loading, signOut, isAuthenticated: !!user }
}