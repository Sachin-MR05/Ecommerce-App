package com.ecommerce.tools.product;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.exception.PaymentException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.model.OrderStatus;
import com.ecommerce.order.CheckoutResponse;
import com.ecommerce.order.OrderItemResponse;
import com.ecommerce.order.OrderResponse;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolResponse;
import com.ecommerce.tools.order.CreateOrderTool;
import com.ecommerce.tools.order.GetOrdersTool;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;

/**
 * Unit tests for CreateOrderTool and GetOrdersTool.
 *
 * Both tools delegate to MerchantCommerceAdapter — mocked here — so these
 * tests verify argument extraction, the userId guard, and the
 * exception→ToolResponse translation in AbstractAgentTool. No database,
 * Spring context, or live HTTP call is needed.
 */
@ExtendWith(MockitoExtension.class)
class SearchProductsEndToEndTest {

    @Mock
    private MerchantCommerceAdapter adapter;

    private CreateOrderTool createOrderTool;
    private GetOrdersTool getOrdersTool;

    private static final Long USER_ID = 42L;

    @BeforeEach
    void setUp() {
        createOrderTool = new CreateOrderTool(adapter);
        getOrdersTool = new GetOrdersTool(adapter);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private CheckoutResponse sampleCheckout() {
        return new CheckoutResponse(100L, "rzp_order_abc123", 29900L, "INR", "rzp_test_key");
    }

    private OrderResponse sampleOrder(Long id, OrderStatus status) {
        return new OrderResponse(
                id,
                status.name(),
                299.00,
                LocalDateTime.now(),
                "rzp_order_abc123",
                null,
                List.of(new OrderItemResponse(10L, "Nike Air", null, 299.00, 1))
        );
    }

    private ToolRequest req(Long userId, Map<String, Object> params) {
        return new ToolRequest(userId, params);
    }

    // -----------------------------------------------------------------------
    // CreateOrderTool — success
    // -----------------------------------------------------------------------

    @Test
    void createOrder_success_returnsCheckoutResponse() {
        CheckoutResponse checkout = sampleCheckout();
        when(adapter.createCheckout(USER_ID)).thenReturn(checkout);

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = createOrderTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(checkout);
        assertThat(response.getErrorCode()).isNull();
    }

    // -----------------------------------------------------------------------
    // CreateOrderTool — failure cases
    // -----------------------------------------------------------------------

    @Test
    void createOrder_missingUserId_returnsValidationError() {
        ToolRequest request = req(null, Map.of());
        ToolResponse response = createOrderTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
    }

    @Test
    void createOrder_emptyCart_returnsPaymentError() {
        when(adapter.createCheckout(USER_ID))
                .thenThrow(new PaymentException("Cannot checkout with an empty cart"));

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = createOrderTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("PAYMENT_ERROR");
        assertThat(response.getErrorMessage()).contains("empty cart");
    }

    @Test
    void createOrder_unexpectedError_returnsInternalError() {
        when(adapter.createCheckout(USER_ID))
                .thenThrow(new RuntimeException("Razorpay connection timeout"));

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = createOrderTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("INTERNAL_ERROR");
        // Internal details must NOT be leaked
        assertThat(response.getErrorMessage()).doesNotContain("Razorpay");
    }

    // -----------------------------------------------------------------------
    // GetOrdersTool — list all orders (no orderId)
    // -----------------------------------------------------------------------

    @Test
    void getOrders_allOrders_returnsOrderList() {
        List<OrderResponse> orders = List.of(
                sampleOrder(1L, OrderStatus.PAID),
                sampleOrder(2L, OrderStatus.CREATED)
        );
        when(adapter.getOrders(USER_ID, null)).thenReturn(orders);

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(orders);
    }

    @Test
    void getOrders_emptyHistory_returnsEmptyList() {
        when(adapter.getOrders(USER_ID, null)).thenReturn(List.of());

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        List<OrderResponse> result = (List<OrderResponse>) response.getData();
        assertThat(result).isEmpty();
    }

    // -----------------------------------------------------------------------
    // GetOrdersTool — single order by id
    // -----------------------------------------------------------------------

    @Test
    void getOrders_singleOrder_returnsOneOrder() {
        OrderResponse order = sampleOrder(1L, OrderStatus.PAID);
        when(adapter.getOrder(USER_ID, 1L, null)).thenReturn(order);

        ToolRequest request = req(USER_ID, Map.of("orderId", 1));
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(order);
    }

    @Test
    void getOrders_singleOrderNotFound_returnsNotFoundError() {
        when(adapter.getOrder(USER_ID, 999L, null))
                .thenThrow(new ResourceNotFoundException("Order not found with id: 999"));

        ToolRequest request = req(USER_ID, Map.of("orderId", 999));
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("NOT_FOUND");
        assertThat(response.getErrorMessage()).contains("999");
    }

    // -----------------------------------------------------------------------
    // GetOrdersTool — failure cases
    // -----------------------------------------------------------------------

    @Test
    void getOrders_missingUserId_returnsValidationError() {
        ToolRequest request = req(null, Map.of());
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
    }

    @Test
    void getOrders_unexpectedError_returnsInternalError() {
        when(adapter.getOrders(anyLong(), isNull()))
                .thenThrow(new RuntimeException("Database unavailable"));

        ToolRequest request = req(USER_ID, Map.of());
        ToolResponse response = getOrdersTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("INTERNAL_ERROR");
        assertThat(response.getErrorMessage()).doesNotContain("Database");
    }
}
