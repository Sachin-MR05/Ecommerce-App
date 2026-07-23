package com.ecommerce.repository;

import com.ecommerce.model.Product;
import com.ecommerce.util.JsonUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository layer - hides the fact that "the database" is a JSON file.
 * Every method does a full read, mutates the in-memory list, then a
 * full write. Simple, but matches the "no database" requirement.
 */
@Repository
public class ProductRepository {

    @Value("${app.data.products-file}")
    private String productsFilePath;

    private final JsonUtil jsonUtil;

    public ProductRepository(JsonUtil jsonUtil) {
        this.jsonUtil = jsonUtil;
    }

    public List<Product> findAll() {
        return jsonUtil.readList(productsFilePath, Product.class);
    }

    public Optional<Product> findById(Long id) {
        return findAll().stream()
                .filter(p -> p.getId().equals(id))
                .findFirst();
    }

    public boolean existsById(Long id) {
        return findById(id).isPresent();
    }

    public Product save(Product product) {
        List<Product> products = findAll();

        long nextId = products.stream()
                .mapToLong(Product::getId)
                .max()
                .orElse(0L) + 1;

        product.setId(nextId);
        products.add(product);
        jsonUtil.writeList(productsFilePath, products);
        return product;
    }

    public Product update(Long id, Product updatedProduct) {
        List<Product> products = findAll();

        for (int i = 0; i < products.size(); i++) {
            if (products.get(i).getId().equals(id)) {
                updatedProduct.setId(id);
                products.set(i, updatedProduct);
                jsonUtil.writeList(productsFilePath, products);
                return updatedProduct;
            }
        }

        return null;
    }

    public boolean deleteById(Long id) {
        List<Product> products = findAll();
        boolean removed = products.removeIf(p -> p.getId().equals(id));

        if (removed) {
            jsonUtil.writeList(productsFilePath, products);
        }

        return removed;
    }
}