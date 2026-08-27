import apiClient from './apiClient';

// GET /cart
export const getCart = () => {
  return apiClient.get('/cart').then((res) => res.data);
};

// POST /cart  { productId, quantity }
export const addToCart = (productId, quantity = 1) => {
  return apiClient.post('/cart', { productId, quantity }).then((res) => res.data);
};

// DELETE /cart/{cartItemId}
export const removeFromCart = (cartItemId) => {
  return apiClient.delete(`/cart/${cartItemId}`).then((res) => res.data);
};

// PUT /cart/{cartItemId}/increase
export const increaseQuantity = (cartItemId) => {
  return apiClient.put(`/cart/${cartItemId}/increase`).then((res) => res.data);
};

// PUT /cart/{cartItemId}/decrease
export const decreaseQuantity = (cartItemId) => {
  return apiClient.put(`/cart/${cartItemId}/decrease`).then((res) => res.data);
};

// DELETE /cart  (clear everything)
export const clearCart = () => {
  return apiClient.delete('/cart');
};
