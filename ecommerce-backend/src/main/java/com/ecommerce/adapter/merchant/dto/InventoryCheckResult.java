package com.ecommerce.adapter.merchant.dto;

/**
 * Structured result for MerchantCommerceAdapter.checkInventory().
 * Lets the AI Agent/Orchestrator decide what to do next instead of
 * having the adapter make that decision (e.g. proceed, ask for a
 * smaller quantity, or tell the user it's out of stock).
 */
public class InventoryCheckResult {

    private Long productId;
    private int requestedQuantity;
    private int availableQuantity;
    private boolean available;

    public InventoryCheckResult() {
    }

    public InventoryCheckResult(Long productId, int requestedQuantity, int availableQuantity, boolean available) {
        this.productId = productId;
        this.requestedQuantity = requestedQuantity;
        this.availableQuantity = availableQuantity;
        this.available = available;
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public int getRequestedQuantity() {
        return requestedQuantity;
    }

    public void setRequestedQuantity(int requestedQuantity) {
        this.requestedQuantity = requestedQuantity;
    }

    public int getAvailableQuantity() {
        return availableQuantity;
    }

    public void setAvailableQuantity(int availableQuantity) {
        this.availableQuantity = availableQuantity;
    }

    public boolean isAvailable() {
        return available;
    }

    public void setAvailable(boolean available) {
        this.available = available;
    }
}
