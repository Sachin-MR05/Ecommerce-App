import { useState, useEffect, useCallback } from 'react';
import * as productService from '../services/productService';

// Encapsulates loading/error/data state for the product list,
// so pages don't repeat the same fetch boilerplate.
export function useProducts(initialSearch = '') {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState(initialSearch);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await productService.getAllProducts(search);
      setProducts(data);
    } catch (err) {
      setError(err.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  return { products, loading, error, search, setSearch, refresh: fetchProducts };
}
