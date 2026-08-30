import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { cart } = useCart();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="topbar">
      <div className="topbar-brand">Ecommerce App</div>
      <div className="topbar-links">
        <Link className="topbar-link" to="/">Home</Link>
        <Link className="topbar-link" to="/agent-info">Agent Info</Link>

        {isAdmin && (
          <Link className="topbar-link" to="/add-product">Add Product</Link>
        )}

        {isAuthenticated && (
          <>
            <Link className="topbar-link" to="/cart">Cart ({cart.totalItems})</Link>
            <Link className="topbar-link" to="/orders">Orders</Link>
          </>
        )}

        {isAuthenticated ? (
          <>
            <span className="topbar-link">
              {user.username} ({user.role})
            </span>
            <button onClick={handleLogout}>Logout</button>
          </>
        ) : (
          <>
            <Link className="topbar-link" to="/login">Login</Link>
            <Link className="topbar-link" to="/register">Register</Link>
          </>
        )}
      </div>
    </nav>
  );
}
