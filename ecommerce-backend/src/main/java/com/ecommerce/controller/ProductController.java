package com.ecommerce.controller;



import com.ecommerce.dto.ProductRequest;
import com.ecommerce.dto.ProductResponse;
import com.ecommerce.model.Product;
import com.ecommerce.service.ProductService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/products")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    // GET /products
    // GET /products?search=lap   (optional search)
    @GetMapping
    public ResponseEntity<List<ProductResponse>> getAllProducts(
            @RequestParam(required = false) String search,
            HttpServletRequest request) {

        String baseUrl = getBaseUrl(request);

        List<Product> products = (search == null || search.isBlank())
                ? productService.getAllProducts()
                : productService.searchProducts(search);

        List<ProductResponse> response = products.stream()
                .map(p -> ProductResponse.fromEntity(p, baseUrl))
                .toList();

        return ResponseEntity.ok(response);
    }

    // GET /products/{id}
    @GetMapping("/{id}")
    public ResponseEntity<ProductResponse> getProductById(@PathVariable Long id, HttpServletRequest request) {
        Product product = productService.getProductById(id);
        return ResponseEntity.ok(ProductResponse.fromEntity(product, getBaseUrl(request)));
    }

    // POST /products
    @PostMapping
    public ResponseEntity<ProductResponse> createProduct(@Valid @RequestBody ProductRequest productRequest,
                                                           HttpServletRequest request) {
        Product created = productService.createProduct(productRequest);
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ProductResponse.fromEntity(created, getBaseUrl(request)));
    }

    // PUT /products/{id}
    @PutMapping("/{id}")
    public ResponseEntity<ProductResponse> updateProduct(@PathVariable Long id,
                                                           @Valid @RequestBody ProductRequest productRequest,
                                                           HttpServletRequest request) {
        Product updated = productService.updateProduct(id, productRequest);
        return ResponseEntity.ok(ProductResponse.fromEntity(updated, getBaseUrl(request)));
    }

    // DELETE /products/{id}
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
        productService.deleteProduct(id);
        return ResponseEntity.noContent().build();
    }

    private String getBaseUrl(HttpServletRequest request) {
        return request.getScheme() + "://" + request.getServerName() + ":" + request.getServerPort();
    }
}