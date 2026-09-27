import axios from 'axios';

const API_BASE_URL = 'https://e-commerce-app-a7grg0h7h9fyb3e4.centralindia-01.azurewebsites.net';

console.log('>>> [ACTIVE API_BASE_URL]:', API_BASE_URL);

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

apiClient.interceptors.request.use((config) => {
  try {
    const raw = localStorage.getItem('ecommerce_auth');
    const auth = raw ? JSON.parse(raw) : null;
    if (auth?.token) {
      config.headers.Authorization = 'Bearer ' + auth.token;
    }
  } catch {}
  return config;
});

export default apiClient;
