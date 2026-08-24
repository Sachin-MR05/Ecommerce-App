package com.ecommerce.tools.product;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.CartItemResponse;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.exception.InsufficientStockException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.tools.cart.AddToCartTool;
import com.ecommerce.tools.cart.RemoveFromCartTool;
import com.ecommerce.tools.cart.UpdateCartTool;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;

/**
 * Unit tests for AddToCartTool, UpdateCartTool, and RemoveFromCartTool.
 *
 * Each tool delegates entirely to MerchantCommerceAdapter — which is mocked
 * here — so these tests verify the tool's own argument validation, user-id
 * guard, and the exception→ToolResponse error-code translation provided by
 * AbstractAgentTool. No database, Spring context, or live HTTP call is needed.
 */
@ExtendWith(MockitoExtension.class)
class ReadOnlyToolsEndToEndTest {

    @Mock
    private MerchantCommerceAdapter adapter;

    private AddToCartTool addToCartTool;
    private UpdateCartTool updateCartTool;
    private RemoveFromCartTool removeFromCartTool;

    private static final Long USER_ID = 42L;

    @BeforeEach
    void setUp() {
        addToCartTool = new AddToCartTool(adapter);
        updateCartTool = new UpdateCartTool(adapter);
        removeFromCartTool = new RemoveFromCartTool(adapter);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private CartResponse cartWith(long cartItemId, long productId, String name, double price, int qty) {
        CartItemResponse item = new CartItemResponse(cartItemId, productId, name, null, price, qty);
        return new CartResponse(List.of(item));
    }

    private ToolRequest req(Long userId, Map<String, Object> params) {
        return new ToolRequest(userId, params);
    }

    // -----------------------------------------------------------------------
    // AddToCartTool — success
    // -----------------------------------------------------------------------

    @Test
    void addToCart_success_returnsCartPayload() {
        CartResponse cart = cartWith(1L, 10L, "Nike Air", 99.99, 2);
        when(adapter.addToCart(USER_ID, 10L, 2)).thenReturn(cart);

        ToolRequest request = req(USER_ID, Map.of("productId", 10, "quantity", 2));
        ToolResponse response = addToCartTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(cart);
        assertThat(response.getErrorCode()).isNull();
    }

    // -----------------------------------------------------------------------
    // AddToCartTool — failure cases
    // -----------------------------------------------------------------------

    @Test
    void addToCart_missingUserId_returnsValidationError() {
        ToolRequest request = req(null, Map.of("productId", 10, "quantity", 2));
        ToolResponse response = addToCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
    }

    @Test
    void addToCart_quantityZero_returnsValidationError() {
        ToolRequest request = req(USER_ID, Map.of("productId", 10, "quantity", 0));
        ToolResponse response = addToCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
        assertThat(response.getErrorMessage()).contains("quantity");
    }

    @Test
    void addToCart_productNotFound_returnsNotFoundError() {
        when(adapter.addToCart(anyLong(), anyLong(), anyInt()))
                .thenThrow(new ResourceNotFoundException("Product not found with id: 999"));

        ToolRequest request = req(USER_ID, Map.of("productId", 999, "quantity", 1));
        ToolResponse response = addToCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("NOT_FOUND");
        assertThat(response.getErrorMessage()).contains("999");
    }

    @Test
    void addToCart_insufficientStock_returnsInsufficientStockError() {
        when(adapter.addToCart(anyLong(), anyLong(), anyInt()))
                .thenThrow(new InsufficientStockException("Only 1 unit(s) of 'Nike Air' available"));

        ToolRequest request = req(USER_ID, Map.of("productId", 10, "quantity", 50));
        ToolResponse response = addToCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("INSUFFICIENT_STOCK");
        assertThat(response.getErrorMessage()).contains("Nike Air");
    }

    // -----------------------------------------------------------------------
    // UpdateCartTool — success
    // -----------------------------------------------------------------------

    @Test
    void updateCart_success_returnsUpdatedCart() {
        CartResponse cart = cartWith(5L, 10L, "Nike Air", 99.99, 3);
        when(adapter.updateCart(USER_ID, 5L, 3)).thenReturn(cart);

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 5, "quantity", 3));
        ToolResponse response = updateCartTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(cart);
    }

    // -----------------------------------------------------------------------
    // UpdateCartTool — failure cases
    // -----------------------------------------------------------------------

    @Test
    void updateCart_missingUserId_returnsValidationError() {
        ToolRequest request = req(null, Map.of("cartItemId", 5, "quantity", 3));
        ToolResponse response = updateCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
    }

    @Test
    void updateCart_negativeQuantity_returnsValidationError() {
        ToolRequest request = req(USER_ID, Map.of("cartItemId", 5, "quantity", -1));
        ToolResponse response = updateCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
        assertThat(response.getErrorMessage()).contains("quantity");
    }

    @Test
    void updateCart_cartItemNotFound_returnsNotFoundError() {
        when(adapter.updateCart(anyLong(), anyLong(), anyInt()))
                .thenThrow(new ResourceNotFoundException("Cart item not found with id: 99"));

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 99, "quantity", 2));
        ToolResponse response = updateCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("NOT_FOUND");
    }

    @Test
    void updateCart_insufficientStock_returnsInsufficientStockError() {
        when(adapter.updateCart(anyLong(), anyLong(), anyInt()))
                .thenThrow(new InsufficientStockException("Only 2 unit(s) of 'Nike Air' available"));

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 5, "quantity", 100));
        ToolResponse response = updateCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("INSUFFICIENT_STOCK");
    }

    // -----------------------------------------------------------------------
    // RemoveFromCartTool — success
    // -----------------------------------------------------------------------

    @Test
    void removeFromCart_success_returnsEmptyCart() {
        CartResponse emptyCart = new CartResponse(List.of());
        when(adapter.removeFromCart(USER_ID, 5L)).thenReturn(emptyCart);

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 5));
        ToolResponse response = removeFromCartTool.execute(request);

        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getData()).isEqualTo(emptyCart);
    }

    // -----------------------------------------------------------------------
    // RemoveFromCartTool — failure cases
    // -----------------------------------------------------------------------

    @Test
    void removeFromCart_missingUserId_returnsValidationError() {
        ToolRequest request = req(null, Map.of("cartItemId", 5));
        ToolResponse response = removeFromCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("VALIDATION_ERROR");
    }

    @Test
    void removeFromCart_cartItemNotFound_returnsNotFoundError() {
        when(adapter.removeFromCart(anyLong(), anyLong()))
                .thenThrow(new ResourceNotFoundException("Cart item not found with id: 77"));

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 77));
        ToolResponse response = removeFromCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("NOT_FOUND");
        assertThat(response.getErrorMessage()).contains("77");
    }

    @Test
    void removeFromCart_unexpectedRuntimeException_returnsInternalError() {
        when(adapter.removeFromCart(anyLong(), anyLong()))
                .thenThrow(new RuntimeException("Database connection lost"));

        ToolRequest request = req(USER_ID, Map.of("cartItemId", 5));
        ToolResponse response = removeFromCartTool.execute(request);

        assertThat(response.isSuccess()).isFalse();
        assertThat(response.getErrorCode()).isEqualTo("INTERNAL_ERROR");
        // Internal details must NOT be leaked to the caller
        assertThat(response.getErrorMessage()).doesNotContain("Database");
    }
}
