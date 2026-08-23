import axios from 'axios';

// Single place to change the backend base URL.
const API_BASE_URL = 'http://localhost:8080';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Attach the logged-in user's JWT (if any) to every request.
apiClient.interceptors.request.use((config) => {
  try {
    const raw = localStorage.getItem('ecommerce_auth');
    const auth = raw ? JSON.parse(raw) : null;
    if (auth?.token) {
      config.headers.Authorization = `Bearer ${auth.token}`;
    }
  } catch {
    // ignore malformed storage
  }
  return config;
});

export default apiClient;
