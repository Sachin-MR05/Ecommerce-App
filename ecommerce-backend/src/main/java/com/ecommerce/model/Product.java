package com.ecommerce.model;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Represents a Product entity.
 * Plain POJO (no Lombok dependency at runtime issues) - explicit getters/setters
 * so the class is readable even without an IDE annotation processor configured.
 */
public class Product {

    private Long id;
    private String name;
    private String description;
    private double price;
    private String category;
    private int stock;
    private String image; // just the filename, e.g. "laptop.jpg"

    public Product() {
    }

    public Product(Long id, String name, String description, double price,
                    String category, int stock, String image) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.price = price;
        this.category = category;
        this.stock = stock;
        this.image = image;
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

    @JsonProperty("image")
    public String getImage() {
        return image;
    }

    public void setImage(String image) {
        this.image = image;
    }
}