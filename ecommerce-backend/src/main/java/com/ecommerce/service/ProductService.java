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
        return productRepository.findByNameContainingIgnoreCaseOrCategoryContainingIgnoreCase(keyword, keyword);
    }

    public Product createProduct(ProductRequest request) {
        Product product = new Product();
        mapRequestToProduct(request, product);
        return productRepository.save(product);
    }

    public Product updateProduct(Long id, ProductRequest request) {
        Product product = getProductById(id); // 404 if it doesn't exist
        mapRequestToProduct(request, product);
        return productRepository.save(product);
    }

    public void deleteProduct(Long id) {
        if (!productRepository.existsById(id)) {
            throw new ResourceNotFoundException("Product not found with id: " + id);
        }
        productRepository.deleteById(id);
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
