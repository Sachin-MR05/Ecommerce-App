import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const EMPTY_FORM = {
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  adminCode: ''
};

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY_FORM);
  const [role, setRole] = useState('CUSTOMER');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    try {
      await register({
        username: form.username,
        email: form.email,
        password: form.password,
        role,
        adminCode: role === 'ADMIN' ? form.adminCode : undefined
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.message || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Register</h1>
      </div>

      {error && <p>Error: {error}</p>}

      <form className="card form-card" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-field">
            <label>Username</label>
            <input name="username" value={form.username} onChange={handleChange} required />
          </div>

          <div className="form-field">
            <label>Email</label>
            <input type="email" name="email" value={form.email} onChange={handleChange} required />
          </div>

          <div className="form-field">
            <label>Password</label>
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
              minLength={6}
            />
          </div>

          <div className="form-field">
            <label>Confirm Password</label>
            <input
              type="password"
              name="confirmPassword"
              value={form.confirmPassword}
              onChange={handleChange}
              required
              minLength={6}
            />
          </div>

          <div className="form-field form-field-full">
            <label>Account Type</label>
            <div className="category-filter-row">
              <button
                type="button"
                className={role === 'CUSTOMER' ? 'filter-chip is-active' : 'filter-chip'}
                onClick={() => setRole('CUSTOMER')}
              >
                Customer
              </button>
              <button
                type="button"
                className={role === 'ADMIN' ? 'filter-chip is-active' : 'filter-chip'}
                onClick={() => setRole('ADMIN')}
              >
                Admin
              </button>
            </div>
          </div>

          {role === 'ADMIN' && (
            <div className="form-field form-field-full">
              <label>Admin Invite Code</label>
              <input
                name="adminCode"
                value={form.adminCode}
                onChange={handleChange}
                required
              />
            </div>
          )}

          <div className="form-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? 'Creating account...' : 'Register'}
            </button>
          </div>
        </div>
      </form>

      <p className="card-meta">
        Already have an account? <Link className="text-link" to="/login">Login</Link>
      </p>
    </div>
  );
}
