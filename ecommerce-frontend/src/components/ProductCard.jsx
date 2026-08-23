import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';

export default function ProductCard({ product, onDelete }) {
  const { addItem } = useCart();
  const { isAuthenticated, isAdmin } = useAuth();
  const navigate = useNavigate();

  const handleAddToCart = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    addItem(product.id, 1);
  };

  return (
    <article className="card product-card">
      {product.imageUrl && (
        <div className="card-media">
          <img src={product.imageUrl} alt={product.name} />
        </div>
      )}

      <div className="card-body">
        <h3 className="card-title">
          <Link className="text-link" to={`/products/${product.id}`}>
            {product.name}
          </Link>
        </h3>
        <p className="card-meta">{product.category}</p>
        <p className="card-price">₹{product.price}</p>
        <p className="card-meta">Stock: {product.stock}</p>
      </div>

      <div className="card-actions">
        <button onClick={handleAddToCart} disabled={product.stock === 0}>
          Add to Cart
        </button>

        {isAdmin && (
          <>
            <Link className="button-link" to={`/edit-product/${product.id}`}>
              Edit
            </Link>

            {onDelete && <button onClick={() => onDelete(product.id)}>Delete</button>}
          </>
        )}
      </div>
    </article>
  );
}
