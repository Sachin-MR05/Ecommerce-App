import React, { useState, useEffect } from 'react';
import * as orderService from '../services/orderService';

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    orderService
      .getOrders()
      .then(setOrders)
      .catch((err) => setError(err.response?.data?.message || err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading orders...</p>;
  if (error) return <p>Error: {error}</p>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Your Orders</h1>
      </div>

      {orders.length === 0 && <p className="empty-state">You haven't placed any orders yet.</p>}

      <div className="stack">
        {orders.map((order) => (
          <div key={order.id} className="card summary-card">
            <div className="page-header">
              <h3>Order #{order.id}</h3>
              <p className="card-meta">{order.status}</p>
            </div>

            <p className="card-meta">
              Placed: {new Date(order.createdAt).toLocaleString()}
            </p>

            <div className="stack">
              {order.items.map((item, index) => (
                <div key={index} className="card cart-item">
                  <div className="cart-item-main">
                    {item.imageUrl && (
                      <div className="card-media cart-media">
                        <img src={item.imageUrl} alt={item.productName} />
                      </div>
                    )}
                    <div className="card-body">
                      <p className="card-title">{item.productName}</p>
                      <p className="card-meta">
                        ₹{item.price} × {item.quantity}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <h3>Total: ₹{order.totalAmount}</h3>
          </div>
        ))}
      </div>
    </div>
  );
}
