import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import * as productService from '../services/productService';
import { useCart } from '../context/CartContext';

export default function ProductDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    productService
      .getProductById(id)
      .then(setProduct)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error}</p>;
  if (!product) return <p>Product not found.</p>;

  return (
    <div className="page">
      <div className="page-header">
        <button onClick={() => navigate(-1)}>Back</button>
      </div>

      <article className="card detail-card">
        <h1 className="card-title">{product.name}</h1>
        {product.imageUrl && <img className="detail-image" src={product.imageUrl} alt={product.name} />}

        <div className="card-body">
          <p>{product.description}</p>
          <p>Category: {product.category}</p>
          <p>Price: ₹{product.price}</p>
          <p>Stock: {product.stock}</p>
        </div>

        <div className="card-actions">
          <button onClick={() => addItem(product.id, 1)} disabled={product.stock === 0}>
            Add to Cart
          </button>
        </div>
      </article>
    </div>
  );
}
