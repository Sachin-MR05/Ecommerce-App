package com.ecommerce.adapter.merchant.dto;

/**
 * Structured result for MerchantCommerceAdapter.getPrice().
 * Always built from a fresh read of the Product entity - never
 * from a value captured earlier during searchProducts()/getProduct(),
 * so the AI Agent can't act on a stale price.
 */
public class PriceInfo {

    private Long productId;
    private double price;
    private String currency;

    public PriceInfo() {
    }

    public PriceInfo(Long productId, double price, String currency) {
        this.productId = productId;
        this.price = price;
        this.currency = currency;
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public double getPrice() {
        return price;
    }

    public void setPrice(double price) {
        this.price = price;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }
}
