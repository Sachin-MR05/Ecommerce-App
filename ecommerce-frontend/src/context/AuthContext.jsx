import React, { createContext, useContext, useState, useCallback } from 'react';
import * as authService from '../services/authService';

const AuthContext = createContext(null);

const STORAGE_KEY = 'ecommerce_auth';

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(loadStoredAuth);
  const [error, setError] = useState(null);

  const persist = (data) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    setAuth(data);
  };

  const login = useCallback(async (email, password) => {
    setError(null);
    try {
      const data = await authService.login(email, password);
      persist(data);
      return data;
    } catch (err) {
      const message = err.response?.data?.message || err.message;
      setError(message);
      throw err;
    }
  }, []);

  const register = useCallback(async (payload) => {
    setError(null);
    try {
      const data = await authService.register(payload);
      persist(data);
      return data;
    } catch (err) {
      const message = err.response?.data?.message || err.message;
      setError(message);
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setAuth(null);
  }, []);

  const value = {
    user: auth, // { token, id, username, email, role } or null
    isAuthenticated: !!auth,
    isAdmin: auth?.role === 'ADMIN',
    error,
    login,
    register,
    logout
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
