package com.ecommerce.dto;

/**
 * A single cart line, enriched with product name/price/image
 * so the frontend doesn't need a second round trip per item.
 */
public class CartItemResponse {

    private Long cartItemId;
    private Long productId;
    private String productName;
    private String image;
    private double price;
    private int quantity;
    private double subtotal;

    public CartItemResponse() {
    }

    public CartItemResponse(Long cartItemId, Long productId, String productName,
                             String image, double price, int quantity) {
        this.cartItemId = cartItemId;
        this.productId = productId;
        this.productName = productName;
        this.image = image;
        this.price = price;
        this.quantity = quantity;
        this.subtotal = price * quantity;
    }

    public Long getCartItemId() {
        return cartItemId;
    }

    public void setCartItemId(Long cartItemId) {
        this.cartItemId = cartItemId;
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public String getProductName() {
        return productName;
    }

    public void setProductName(String productName) {
        this.productName = productName;
    }

    public String getImage() {
        return image;
    }

    public void setImage(String image) {
        this.image = image;
    }

    public double getPrice() {
        return price;
    }

    public void setPrice(double price) {
        this.price = price;
    }

    public int getQuantity() {
        return quantity;
    }

    public void setQuantity(int quantity) {
        this.quantity = quantity;
    }

    public double getSubtotal() {
        return subtotal;
    }

    public void setSubtotal(double subtotal) {
        this.subtotal = subtotal;
    }
}