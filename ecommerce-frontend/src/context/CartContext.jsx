import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as cartService from '../services/cartService';
import { useAuth } from './AuthContext';

const CartContext = createContext(null);

const EMPTY_CART = { items: [], total: 0, totalItems: 0 };

export function CartProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [cart, setCart] = useState(EMPTY_CART);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refreshCart = useCallback(async () => {
    if (!isAuthenticated) {
      setCart(EMPTY_CART);
      return;
    }
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
  }, [isAuthenticated]);

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
    setCart(EMPTY_CART);
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
