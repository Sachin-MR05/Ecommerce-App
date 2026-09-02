import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { openRazorpayCheckout } from '../utils/razorpay';
import * as orderService from '../services/orderService';
import { useAuth } from '../context/AuthContext';

export default function Checkout() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paidSuccess, setPaidSuccess] = useState(false);

  const keyId = searchParams.get('key');
  const razorpayOrderId = searchParams.get('order_id');
  const amount = searchParams.get('amount');
  const currency = searchParams.get('currency') || 'INR';

  useEffect(() => {
    if (!keyId || !razorpayOrderId || !amount) {
      setError('Invalid payment parameters. Please ensure key, order_id, and amount are supplied.');
      setLoading(false);
      return;
    }

    const checkoutData = {
      keyId,
      razorpayOrderId,
      amount: parseInt(amount, 10),
      currency
    };

    setLoading(true);
    openRazorpayCheckout({
      checkoutData,
      user,
      onSuccess: async (payload) => {
        try {
          await orderService.verifyPayment(payload);
          setPaidSuccess(true);
          if (user) {
            setTimeout(() => navigate('/orders'), 2000);
          }
        } catch (err) {
          setError(err.response?.data?.message || err.message);
        } finally {
          setLoading(false);
        }
      },
      onFailure: (err) => {
        setError(err.message);
        setLoading(false);
      },
      onDismiss: () => {
        setLoading(false);
        setError('Payment dismissed by user.');
      }
    });
  }, [keyId, razorpayOrderId, amount, currency, user, navigate]);

  if (paidSuccess) {
    return (
      <div style={{ maxWidth: '500px', margin: '80px auto', textAlign: 'center', padding: '30px', border: '1px solid #111', borderRadius: '12px', background: '#fff' }}>
        <div style={{ fontSize: '48px', marginBottom: '10px' }}>🎉</div>
        <h2 style={{ color: '#2ecc71', margin: '0 0 10px 0' }}>Payment Successful!</h2>
        <p style={{ color: '#555', fontSize: '15px' }}>
          Your payment has been verified. Thank you for your purchase!
        </p>
        <button
          onClick={() => navigate('/')}
          style={{ background: '#111', color: '#fff', border: 'none', padding: '10px 24px', fontSize: '14px', borderRadius: '6px', cursor: 'pointer', marginTop: '15px' }}
        >
          Return to Shop
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '500px', margin: '80px auto', textAlign: 'center' }}>
      <h2>Payment Checkout</h2>
      {loading && <p>Opening Razorpay Secure Checkout Widget...</p>}
      {error && (
        <div style={{ background: '#fce8e6', color: '#c5221f', padding: '15px', borderRadius: '6px', border: '1px solid #ea4335', marginTop: '20px' }}>
          {error}
        </div>
      )}
      <button 
        onClick={() => window.location.reload()} 
        style={{ background: '#528FF0', color: 'white', border: 'none', padding: '12px 30px', fontSize: '15px', borderRadius: '6px', cursor: 'pointer', marginTop: '20px' }}
      >
        Retry Payment
      </button>
    </div>
  );
}
