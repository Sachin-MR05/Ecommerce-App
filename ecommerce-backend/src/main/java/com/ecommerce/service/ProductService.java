package com.ecommerce.service;

import com.ecommerce.dto.ProductRequest;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.model.Product;
import com.ecommerce.repository.ProductRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ProductService {

    private final ProductRepository productRepository;

    public ProductService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    public List<Product> getAllProducts() {
        return productRepository.findAll();
    }

    public Product getProductById(Long id) {
        return productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found with id: " + id));
    }

    public List<Product> searchProducts(String keyword) {
        String lower = keyword.toLowerCase();
        return productRepository.findAll().stream()
                .filter(p -> p.getName().toLowerCase().contains(lower)
                        || (p.getCategory() != null && p.getCategory().toLowerCase().contains(lower)))
                .toList();
    }

    public Product createProduct(ProductRequest request) {
        Product product = new Product();
        mapRequestToProduct(request, product);
        return productRepository.save(product);
    }

    public Product updateProduct(Long id, ProductRequest request) {
        // ensures a clean 404 if the id doesn't exist, instead of
        // silently doing nothing
        getProductById(id);

        Product product = new Product();
        mapRequestToProduct(request, product);

        Product updated = productRepository.update(id, product);
        if (updated == null) {
            throw new ResourceNotFoundException("Product not found with id: " + id);
        }
        return updated;
    }

    public void deleteProduct(Long id) {
        boolean deleted = productRepository.deleteById(id);
        if (!deleted) {
            throw new ResourceNotFoundException("Product not found with id: " + id);
        }
    }

    private void mapRequestToProduct(ProductRequest request, Product product) {
        product.setName(request.getName());
        product.setDescription(request.getDescription());
        product.setPrice(request.getPrice());
        product.setCategory(request.getCategory());
        product.setStock(request.getStock());
        product.setImage(request.getImage());
    }
}