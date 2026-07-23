import React from 'react';
import { useCart } from '../context/CartContext';
import CartItem from '../components/CartItem';

export default function Cart() {
  const { cart, loading, error, clear } = useCart();

  if (loading) return <p>Loading cart...</p>;
  if (error) return <p>Error: {error}</p>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Your Cart</h1>
      </div>

      {cart.items.length === 0 && <p className="empty-state">Cart is empty.</p>}

      <div className="stack">
        {cart.items.map((item) => (
          <CartItem key={item.cartItemId} item={item} />
        ))}
      </div>

      {cart.items.length > 0 && (
        <div className="card summary-card">
          <h3>Total Items: {cart.totalItems}</h3>
          <h3>Total: ₹{cart.total}</h3>
          <button onClick={clear}>Clear Cart</button>
        </div>
      )}
    </div>
  );
}
