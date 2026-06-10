import axios from 'axios';

const BASE = 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE,
  timeout: 120000,
  withCredentials: true, // Required for sharing cookies with backend
  headers: {
    'Content-Type': 'application/json',
  },
});

// No longer needs to inject token manually as we use HTTP-only cookies
// But we keep the interceptor structure if we need to handle specific logic later

export default api;
