import apiClient from './apiClient';

// GET /products  (optionally ?search=keyword)
export const getAllProducts = (search = '') => {
  const params = search ? { search } : {};
  return apiClient.get('/products', { params }).then((res) => res.data);
};

// GET /products/{id}
export const getProductById = (id) => {
  return apiClient.get(`/products/${id}`).then((res) => res.data);
};

// POST /products
export const createProduct = (productData) => {
  return apiClient.post('/products', productData).then((res) => res.data);
};

// PUT /products/{id}
export const updateProduct = (id, productData) => {
  return apiClient.put(`/products/${id}`, productData).then((res) => res.data);
};

// DELETE /products/{id}
export const deleteProduct = (id) => {
  return apiClient.delete(`/products/${id}`);
};
