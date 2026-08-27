package com.ecommerce.order;

import com.ecommerce.model.OrderItem;

public class OrderItemResponse {

    private Long productId;
    private String productName;
    private String imageUrl;
    private double price;
    private int quantity;

    public OrderItemResponse(Long productId, String productName, String imageUrl, double price, int quantity) {
        this.productId = productId;
        this.productName = productName;
        this.imageUrl = imageUrl;
        this.price = price;
        this.quantity = quantity;
    }

    public static OrderItemResponse fromEntity(OrderItem item, String baseUrl) {
        String imageUrl = item.getProductImage() != null
                ? baseUrl + "/images/" + item.getProductImage()
                : null;
        return new OrderItemResponse(item.getProductId(), item.getProductName(), imageUrl,
                item.getPrice(), item.getQuantity());
    }

    public Long getProductId() {
        return productId;
    }

    public String getProductName() {
        return productName;
    }

    public String getImageUrl() {
        return imageUrl;
    }

    public double getPrice() {
        return price;
    }

    public int getQuantity() {
        return quantity;
    }
}
