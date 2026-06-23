import axios from 'axios'
import { supabase } from './supabase'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',  // direct URL, not proxy
  timeout: 60000,
})

// Attach Supabase JWT to every request
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  console.log('Session token:', session?.access_token ? 'EXISTS' : 'MISSING')  
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// Remove the signOut call — it was causing the infinite loop
api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error)
  }
)

export default api