package com.ecommerce.repository;

import com.ecommerce.model.Product;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * Spring Data JPA repository - "the database" is now a real
 * PostgreSQL "products" table instead of a JSON file.
 */
public interface ProductRepository extends JpaRepository<Product, Long> {

    List<Product> findByNameContainingIgnoreCaseOrCategoryContainingIgnoreCase(String name, String category);
}
