import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ProductForm from '../components/ProductForm';
import * as productService from '../services/productService';

export default function EditProduct() {
  const { id } = useParams();
  const navigate = useNavigate();

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

  const handleSubmit = async (formData) => {
    try {
      await productService.updateProduct(id, formData);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.message || err.message);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (!product) return <p>Product not found.</p>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Edit Product</h1>
      </div>
      {error && <p>Error: {error}</p>}
      <ProductForm initialData={product} onSubmit={handleSubmit} submitLabel="Update Product" />
    </div>
  );
}
