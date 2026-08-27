import apiClient from './apiClient';

// POST /auth/login  { email, password }
export const login = (email, password) => {
  return apiClient.post('/auth/login', { email, password }).then((res) => res.data);
};

// POST /auth/register  { username, email, password, role, adminCode }
export const register = ({ username, email, password, role, adminCode }) => {
  return apiClient
    .post('/auth/register', { username, email, password, role, adminCode })
    .then((res) => res.data);
};
