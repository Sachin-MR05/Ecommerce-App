import React from 'react';
import { Link } from 'react-router-dom';
import { useCart } from '../context/CartContext';

export default function Navbar() {
  const { cart } = useCart();

  return (
    <nav className="topbar">
      <div className="topbar-brand">Ecommerce App</div>
      <div className="topbar-links">
        <Link className="topbar-link" to="/">Home</Link>
        <Link className="topbar-link" to="/add-product">Add Product</Link>
        <Link className="topbar-link" to="/cart">Cart ({cart.totalItems})</Link>
      </div>
    </nav>
  );
}
