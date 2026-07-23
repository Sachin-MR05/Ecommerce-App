import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ProductForm from '../components/ProductForm';
import * as productService from '../services/productService';

export default function AddProduct() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  const handleSubmit = async (formData) => {
    try {
      await productService.createProduct(formData);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.message || err.message);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Add Product</h1>
      </div>
      {error && <p>Error: {error}</p>}
      <ProductForm initialData={null} onSubmit={handleSubmit} submitLabel="Add Product" />
    </div>
  );
}
