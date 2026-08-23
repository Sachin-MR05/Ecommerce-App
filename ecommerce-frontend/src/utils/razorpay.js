// Wraps window.Razorpay (loaded via the <script> tag in index.html) so
// components don't have to deal with the raw widget API directly.
export function openRazorpayCheckout({ checkoutData, user, onSuccess, onFailure, onDismiss }) {
  if (typeof window.Razorpay === 'undefined') {
    onFailure(new Error('Payment widget failed to load. Check your internet connection and try again.'));
    return;
  }

  const options = {
    key: checkoutData.keyId,
    amount: checkoutData.amount,
    currency: checkoutData.currency,
    name: 'Ecommerce App',
    description: `Order #${checkoutData.orderId}`,
    order_id: checkoutData.razorpayOrderId,
    prefill: {
      name: user?.username || '',
      email: user?.email || ''
    },
    theme: {
      color: '#111111'
    },
    handler: function (response) {
      onSuccess({
        razorpayOrderId: response.razorpay_order_id,
        razorpayPaymentId: response.razorpay_payment_id,
        razorpaySignature: response.razorpay_signature
      });
    },
    modal: {
      ondismiss: function () {
        if (onDismiss) onDismiss();
      }
    }
  };

  const razorpay = new window.Razorpay(options);

  razorpay.on('payment.failed', function (response) {
    onFailure(new Error(response.error?.description || 'Payment failed'));
  });

  razorpay.open();
}
