package com.ecommerce.dto;

import java.util.List;

/**
 * Returned by GET /cart - all line items plus the grand total.
 */
public class CartResponse {

    private List<CartItemResponse> items;
    private double total;
    private int totalItems;

    public CartResponse() {
    }

    public CartResponse(List<CartItemResponse> items) {
        this.items = items;
        this.total = items.stream().mapToDouble(CartItemResponse::getSubtotal).sum();
        this.totalItems = items.stream().mapToInt(CartItemResponse::getQuantity).sum();
    }

    public List<CartItemResponse> getItems() {
        return items;
    }

    public void setItems(List<CartItemResponse> items) {
        this.items = items;
    }

    public double getTotal() {
        return total;
    }

    public void setTotal(double total) {
        this.total = total;
    }

    public int getTotalItems() {
        return totalItems;
    }

    public void setTotalItems(int totalItems) {
        this.totalItems = totalItems;
    }
}