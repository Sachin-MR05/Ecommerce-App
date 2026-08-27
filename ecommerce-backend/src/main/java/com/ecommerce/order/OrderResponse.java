package com.ecommerce.order;

import com.ecommerce.model.Order;

import java.time.LocalDateTime;
import java.util.List;

public class OrderResponse {

    private Long id;
    private String status;
    private double totalAmount;
    private LocalDateTime createdAt;
    private String razorpayOrderId;
    private String razorpayPaymentId;
    private List<OrderItemResponse> items;

    public OrderResponse(Long id, String status, double totalAmount, LocalDateTime createdAt,
                          String razorpayOrderId, String razorpayPaymentId, List<OrderItemResponse> items) {
        this.id = id;
        this.status = status;
        this.totalAmount = totalAmount;
        this.createdAt = createdAt;
        this.razorpayOrderId = razorpayOrderId;
        this.razorpayPaymentId = razorpayPaymentId;
        this.items = items;
    }

    public static OrderResponse fromEntity(Order order, String baseUrl) {
        List<OrderItemResponse> items = order.getItems().stream()
                .map(item -> OrderItemResponse.fromEntity(item, baseUrl))
                .toList();

        return new OrderResponse(
                order.getId(),
                order.getStatus().name(),
                order.getTotalAmount(),
                order.getCreatedAt(),
                order.getRazorpayOrderId(),
                order.getRazorpayPaymentId(),
                items
        );
    }

    public Long getId() {
        return id;
    }

    public String getStatus() {
        return status;
    }

    public double getTotalAmount() {
        return totalAmount;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public String getRazorpayOrderId() {
        return razorpayOrderId;
    }

    public String getRazorpayPaymentId() {
        return razorpayPaymentId;
    }

    public List<OrderItemResponse> getItems() {
        return items;
    }
}
