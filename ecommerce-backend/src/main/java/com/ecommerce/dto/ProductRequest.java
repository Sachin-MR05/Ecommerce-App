package com.ecommerce.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;

/**
 * What the client sends when creating/updating a product.
 * No "id" here - the server controls id generation.
 */
public class ProductRequest {

    @NotBlank(message = "Product name is required")
    private String name;

    private String description;

    @Positive(message = "Price must be greater than 0")
    private double price;

    @NotBlank(message = "Category is required")
    private String category;

    @Min(value = 0, message = "Stock cannot be negative")
    private int stock;

    private String image;

    public ProductRequest() {
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
}