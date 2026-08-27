import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import CartItem from '../components/CartItem';
import * as orderService from '../services/orderService';
import { openRazorpayCheckout } from '../utils/razorpay';

export default function Cart() {
  const { cart, loading, error, clear, refreshCart } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [paying, setPaying] = useState(false);
  const [paymentError, setPaymentError] = useState(null);

  const handleCheckout = async () => {
    setPaymentError(null);
    setPaying(true);
    try {
      const checkoutData = await orderService.checkout();

      openRazorpayCheckout({
        checkoutData,
        user,
        onSuccess: async (payload) => {
          try {
            await orderService.verifyPayment(payload);
            await refreshCart();
            navigate('/orders');
          } catch (err) {
            setPaymentError(err.response?.data?.message || err.message);
          } finally {
            setPaying(false);
          }
        },
        onFailure: (err) => {
          setPaymentError(err.message);
          setPaying(false);
        },
        onDismiss: () => {
          setPaying(false);
        }
      });
    } catch (err) {
      setPaymentError(err.response?.data?.message || err.message);
      setPaying(false);
    }
  };

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

          {paymentError && <p>Error: {paymentError}</p>}

          <div className="card-actions">
            <button onClick={handleCheckout} disabled={paying}>
              {paying ? 'Processing...' : 'Checkout & Pay'}
            </button>
            <button onClick={clear} disabled={paying}>
              Clear Cart
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
