import React, { useEffect, useRef, useState } from 'react';

const EMPTY_FORM = {
  name: '',
  description: '',
  price: '',
  category: '',
  stock: '',
  image: ''
};

// Shared by AddProduct.jsx and EditProduct.jsx.
// `initialData` is null for "add" mode, or a product object for "edit" mode.
export default function ProductForm({ initialData, onSubmit, submitLabel = 'Save' }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (initialData) {
      const initialImage = initialData.image || '';
      setForm({
        name: initialData.name || '',
        description: initialData.description || '',
        price: initialData.price ?? '',
        category: initialData.category || '',
        stock: initialData.stock ?? '',
        image: initialImage
      });
      setSelectedFileName(initialImage);
    }
  }, [initialData]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleFile = (file) => {
    if (!file) return;
    setForm((prev) => ({ ...prev, image: file.name }));
    setSelectedFileName(file.name);
  };

  const handleFileInputChange = (e) => {
    handleFile(e.target.files?.[0]);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDraggingFile(false);
    handleFile(e.dataTransfer.files?.[0]);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...form,
      price: parseFloat(form.price),
      stock: parseInt(form.stock, 10)
    });
  };

  return (
    <form className="card form-card" onSubmit={handleSubmit}>
      <div className="form-grid">
        <div className="form-field">
          <label>Name</label>
          <input name="name" value={form.name} onChange={handleChange} required />
        </div>

        <div className="form-field form-field-full">
          <label>Description</label>
          <textarea name="description" value={form.description} onChange={handleChange} />
        </div>

        <div className="form-field">
          <label>Price</label>
          <input type="number" name="price" value={form.price} onChange={handleChange} required min="0" step="0.01" />
        </div>

        <div className="form-field">
          <label>Category</label>
          <input name="category" value={form.category} onChange={handleChange} required />
        </div>

        <div className="form-field">
          <label>Stock</label>
          <input type="number" name="stock" value={form.stock} onChange={handleChange} required min="0" />
        </div>

        <div className="form-field form-field-full">
          <label>Image</label>
          <div
            className={isDraggingFile ? 'drop-zone is-dragging' : 'drop-zone'}
            onDragEnter={(e) => {
              e.preventDefault();
              setIsDraggingFile(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDraggingFile(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsDraggingFile(false);
            }}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="file-input"
              onChange={handleFileInputChange}
            />
            <strong>Drop an image here or click to choose a file</strong>
            <span>
              {selectedFileName || 'No image selected'}
            </span>
          </div>
          <input type="hidden" name="image" value={form.image} />
        </div>

        <div className="form-actions">
          <button type="submit">{submitLabel}</button>
        </div>
      </div>
    </form>
  );
}
