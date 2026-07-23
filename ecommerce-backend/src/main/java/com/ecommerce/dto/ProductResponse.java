package com.ecommerce.dto;

import com.ecommerce.model.Product;

/**
 * What the server sends back to the client.
 * Adds a fully-qualified imageUrl so the React frontend doesn't
 * have to know the backend's base URL convention.
 */
public class ProductResponse {

    private Long id;
    private String name;
    private String description;
    private double price;
    private String category;
    private int stock;
    private String image;
    private String imageUrl;

    public ProductResponse() {
    }

    public static ProductResponse fromEntity(Product product, String baseUrl) {
        ProductResponse response = new ProductResponse();
        response.setId(product.getId());
        response.setName(product.getName());
        response.setDescription(product.getDescription());
        response.setPrice(product.getPrice());
        response.setCategory(product.getCategory());
        response.setStock(product.getStock());
        response.setImage(product.getImage());

        if (product.getImage() != null && !product.getImage().isBlank()) {
            response.setImageUrl(baseUrl + "/images/" + product.getImage());
        }

        return response;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public double getPrice() {
        return price;
    }

    public void setPrice(double price) {
        this.price = price;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public int getStock() {
        return stock;
    }

    public void setStock(int stock) {
        this.stock = stock;
    }

    public String getImage() {
        return image;
    }

    public void setImage(String image) {
        this.image = image;
    }

    public String getImageUrl() {
        return imageUrl;
    }

    public void setImageUrl(String imageUrl) {
        this.imageUrl = imageUrl;
    }
}