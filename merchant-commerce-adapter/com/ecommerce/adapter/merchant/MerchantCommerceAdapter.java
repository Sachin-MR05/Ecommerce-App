package com.ecommerce.adapter.merchant;

import com.ecommerce.adapter.merchant.dto.InventoryCheckResult;
import com.ecommerce.adapter.merchant.dto.PaymentVerificationResult;
import com.ecommerce.adapter.merchant.dto.PriceInfo;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.dto.ProductResponse;
import com.ecommerce.order.CheckoutResponse;
import com.ecommerce.order.OrderResponse;
import com.ecommerce.order.VerifyPaymentRequest;

import java.util.List;

/**
 * Commerce interface between the AI Agent/Agent Orchestrator and this
 * merchant's existing service layer.
 *
 * This is intentionally a thin, trusted-information-and-execution surface:
 * - It contains no database access (delegates to the existing Service layer).
 * - It contains no duplicated business logic (pricing, stock, payment
 *   verification, etc. all live where they already live).
 * - It contains no AI decision-making - the AI Agent decides *what* to buy
 *   and *when*; this adapter only executes the requested commerce operation
 *   and returns trusted data.
 *
 * Implementations are expected to be swappable so a second merchant backend
 * can later be plugged in behind the same contract.
 *
 * baseUrl parameters are the same "scheme://host:port" value the existing
 * controllers derive from HttpServletRequest, used only to build absolute
 * image URLs. When the caller has no HTTP request context (e.g. an agent
 * orchestrator calling this in-process), pass null or "" - image URLs will
 * simply be omitted.
 */
public interface MerchantCommerceAdapter {

    /**
     * Searches the existing product catalog by keyword (matches name or
     * category, same as the existing /products?search= endpoint). A null or
     * blank keyword returns the full catalog.
     */
    List<ProductResponse> searchProducts(String keyword, String baseUrl);

    /**
     * Retrieves complete product information by id.
     * Throws com.ecommerce.exception.ResourceNotFoundException if the product doesn't exist.
     */
    ProductResponse getProduct(Long productId, String baseUrl);

    /**
     * Checks whether requestedQuantity units of a product are currently available.
     * Returns a structured result - never throws for an insufficient-stock case,
     * so the AI Agent can decide how to proceed instead of the adapter deciding
     * for it. Still throws ResourceNotFoundException if the product itself doesn't exist.
     */
    InventoryCheckResult checkInventory(Long productId, int requestedQuantity);

    /**
     * Returns the current, live price for a product - always re-read from the
     * product record, never a value cached from an earlier searchProducts()/
     * getProduct() call.
     * Throws ResourceNotFoundException if the product doesn't exist.
     */
    PriceInfo getPrice(Long productId);

    /**
     * Adds a product/quantity to the given user's cart.
     * Throws ResourceNotFoundException if the product doesn't exist, or
     * InsufficientStockException if the resulting quantity exceeds stock.
     */
    CartResponse addToCart(Long userId, Long productId, int quantity);

    /**
     * Sets an existing cart item to an absolute quantity (not a delta).
     * A quantity of 0 or less removes the item, mirroring the existing
     * cart-decrease-to-zero behavior.
     * Throws ResourceNotFoundException if the cart item doesn't belong to
     * the user or doesn't exist, or InsufficientStockException if the
     * requested quantity exceeds stock.
     */
    CartResponse updateCart(Long userId, Long cartItemId, int quantity);

    /**
     * Removes a cart item entirely.
     * Throws ResourceNotFoundException if the cart item doesn't exist or
     * doesn't belong to the user.
     */
    CartResponse removeFromCart(Long userId, Long cartItemId);

    /**
     * Validates the user's current cart (availability + live pricing),
     * computes the total, and creates the order/Razorpay-checkout
     * representation the frontend/agent needs to hand off to Razorpay.
     * Throws PaymentException if the cart is empty or a line item no
     * longer has sufficient stock.
     */
    CheckoutResponse createCheckout(Long userId);

    /**
     * Retrieves an order by id (scoped to the given user), including its
     * current status - suitable for order/delivery tracking.
     * Throws ResourceNotFoundException if the order doesn't exist or
     * doesn't belong to the user.
     */
    OrderResponse getOrder(Long userId, Long orderId, String baseUrl);

    /**
     * Server-side verification of a payment via the existing Razorpay
     * integration. Never trusts a client-reported "payment successful"
     * state - this always re-verifies the signature against Razorpay.
     * The order is only marked PAID, and only returned on the result,
     * when verification actually succeeds. Invalid payment/order id,
     * invalid signature, and payment failure are all reported as a
     * non-exceptional, structured "not verified" result.
     */
    PaymentVerificationResult verifyPayment(Long userId, VerifyPaymentRequest request, String baseUrl);
}
