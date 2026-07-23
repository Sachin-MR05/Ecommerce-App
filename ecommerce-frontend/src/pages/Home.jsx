import React from 'react';
import { useProducts } from '../hooks/useProducts';
import ProductCard from '../components/ProductCard';
import * as productService from '../services/productService';
import { useState } from 'react';

export default function Home() {
  const { products, loading, error, search, setSearch, refresh } = useProducts();
  const [activeCategory, setActiveCategory] = useState('all');

  const handleDelete = async (id) => {
    await productService.deleteProduct(id);
    refresh();
  };

  const categories = Array.from(
    new Set(products.map((product) => (product.category || '').trim()).filter(Boolean))
  ).sort((left, right) => left.localeCompare(right));

  const visibleProducts =
    activeCategory === 'all'
      ? products
      : products.filter((product) => (product.category || '').trim() === activeCategory);

  if (loading) return <p>Loading products...</p>;
  if (error) return <p>Error: {error}</p>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Products</h1>

        <input
          className="search-input"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="category-filter-row" aria-label="Product categories">
        <button
          type="button"
          className={activeCategory === 'all' ? 'filter-chip is-active' : 'filter-chip'}
          onClick={() => setActiveCategory('all')}
        >
          All
        </button>

        {categories.map((category) => (
          <button
            key={category}
            type="button"
            className={activeCategory === category ? 'filter-chip is-active' : 'filter-chip'}
            onClick={() => setActiveCategory(category)}
          >
            {category}
          </button>
        ))}
      </div>

      {visibleProducts.length === 0 && <p className="empty-state">No products found.</p>}

      <div className="card-grid">
        {visibleProducts.map((product) => (
          <ProductCard key={product.id} product={product} onDelete={handleDelete} />
        ))}
      </div>
    </div>
  );
}
