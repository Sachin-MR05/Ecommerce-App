import React from 'react';
import { useCart } from '../context/CartContext';

const API_BASE_URL = 'https://e-commerce-app-a7grg0h7h9fyb3e4.centralindia-01.azurewebsites.net';

export default function CartItem({ item }) {
  const { increase, decrease, removeItem } = useCart();

  return (
    <article className="card cart-item">
      <div className="cart-item-main">
        {item.image && (
          <div className="card-media cart-media">
<img src={`${API_BASE_URL}/images/${item.image}`} alt={item.productName} />          </div>
        )}

        <div className="card-body">
          <h3 className="card-title">{item.productName}</h3>
          <p className="card-meta">?{item.price}</p>
          <p className="card-meta">Subtotal: ?{item.subtotal}</p>
        </div>
      </div>

      <div className="card-actions cart-actions">
        <button onClick={() => decrease(item.cartItemId)}>-</button>
        <span className="quantity-label">{item.quantity}</span>
        <button onClick={() => increase(item.cartItemId)}>+</button>
        <button onClick={() => removeItem(item.cartItemId)}>Remove</button>
      </div>
    </article>
  );
}
