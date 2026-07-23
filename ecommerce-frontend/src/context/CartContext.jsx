import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as cartService from '../services/cartService';

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [cart, setCart] = useState({ items: [], total: 0, totalItems: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refreshCart = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await cartService.getCart();
      setCart(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshCart();
  }, [refreshCart]);

  const addItem = async (productId, quantity = 1) => {
    const data = await cartService.addToCart(productId, quantity);
    setCart(data);
  };

  const removeItem = async (cartItemId) => {
    const data = await cartService.removeFromCart(cartItemId);
    setCart(data);
  };

  const increase = async (cartItemId) => {
    const data = await cartService.increaseQuantity(cartItemId);
    setCart(data);
  };

  const decrease = async (cartItemId) => {
    const data = await cartService.decreaseQuantity(cartItemId);
    setCart(data);
  };

  const clear = async () => {
    await cartService.clearCart();
    setCart({ items: [], total: 0, totalItems: 0 });
  };

  const value = {
    cart,
    loading,
    error,
    refreshCart,
    addItem,
    removeItem,
    increase,
    decrease,
    clear
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

// Custom hook for consuming the cart context anywhere in the app
export function useCart() {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}
