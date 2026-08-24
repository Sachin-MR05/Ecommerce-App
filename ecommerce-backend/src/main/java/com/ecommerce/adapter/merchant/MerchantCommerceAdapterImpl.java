package com.ecommerce.adapter.merchant;

import com.ecommerce.adapter.merchant.dto.InventoryCheckResult;
import com.ecommerce.adapter.merchant.dto.PaymentVerificationResult;
import com.ecommerce.adapter.merchant.dto.PriceInfo;
import com.ecommerce.dto.CartItemRequest;
import com.ecommerce.dto.CartItemResponse;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.dto.ProductResponse;
import com.ecommerce.exception.PaymentException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.model.Product;
import com.ecommerce.order.CheckoutResponse;
import com.ecommerce.order.OrderResponse;
import com.ecommerce.order.OrderService;
import com.ecommerce.order.RazorpayService;
import com.ecommerce.order.VerifyPaymentRequest;
import com.ecommerce.service.CartService;
import com.ecommerce.service.ProductService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Default MerchantCommerceAdapter implementation for this merchant.
 *
 * Every operation delegates to the existing ProductService, CartService,
 * OrderService and RazorpayService - the same services the existing
 * controllers use. No repository/database access happens here, and no
 * product/cart/order/payment business rule is reimplemented here.
 */
@Service
public class MerchantCommerceAdapterImpl implements MerchantCommerceAdapter {

    private final ProductService productService;
    private final CartService cartService;
    private final OrderService orderService;
    private final RazorpayService razorpayService;

    public MerchantCommerceAdapterImpl(ProductService productService,
                                        CartService cartService,
                                        OrderService orderService,
                                        RazorpayService razorpayService) {
        this.productService = productService;
        this.cartService = cartService;
        this.orderService = orderService;
        this.razorpayService = razorpayService;
    }

    @Override
    public List<ProductResponse> searchProducts(String keyword, String baseUrl) {
        List<Product> products = (keyword == null || keyword.isBlank())
                ? productService.getAllProducts()
                : productService.searchProducts(keyword);

        String resolvedBaseUrl = resolveBaseUrl(baseUrl);
        return products.stream()
                .map(product -> ProductResponse.fromEntity(product, resolvedBaseUrl))
                .toList();
    }

    @Override
    public ProductResponse getProduct(Long productId, String baseUrl) {
        Product product = productService.getProductById(productId);
        return ProductResponse.fromEntity(product, resolveBaseUrl(baseUrl));
    }

    @Override
    public InventoryCheckResult checkInventory(Long productId, int requestedQuantity) {
        Product product = productService.getProductById(productId);
        int availableQuantity = product.getStock();
        boolean available = requestedQuantity > 0 && requestedQuantity <= availableQuantity;
        return new InventoryCheckResult(productId, requestedQuantity, availableQuantity, available);
    }

    @Override
    public PriceInfo getPrice(Long productId) {
        // Always re-reads the product record - never a value carried over
        // from an earlier search/getProduct() call - so the price can't be stale.
        Product product = productService.getProductById(productId);
        return new PriceInfo(productId, product.getPrice(), razorpayService.getCurrency());
    }

    @Override
    public CartResponse addToCart(Long userId, Long productId, int quantity) {
        CartItemRequest request = new CartItemRequest();
        request.setProductId(productId);
        request.setQuantity(quantity);
        return cartService.addToCart(userId, request);
    }

    @Override
    public CartResponse updateCart(Long userId, Long cartItemId, int quantity) {
        if (quantity <= 0) {
            return cartService.removeFromCart(userId, cartItemId);
        }

        CartItemResponse existingItem = findOwnedCartItem(userId, cartItemId);
        int delta = quantity - existingItem.getQuantity();

        // CartService only exposes +/-1 step changes (increaseQuantity/decreaseQuantity),
        // which already reuse its existing stock-check logic. Rather than adding a new
        // method to CartService, updateCart() drives it via those same existing calls so
        // this change stays fully contained to the adapter package. For carts with very
        // large quantity jumps, adding a CartService.setQuantity(...) that reuses its
        // existing checkStock()/getOwnedItem() helpers would be a cleaner, O(1) follow-up.
        CartResponse result = null;
        if (delta > 0) {
            for (int i = 0; i < delta; i++) {
                result = cartService.increaseQuantity(userId, cartItemId);
            }
        } else if (delta < 0) {
            for (int i = 0; i < -delta; i++) {
                result = cartService.decreaseQuantity(userId, cartItemId);
            }
        } else {
            result = cartService.getCart(userId);
        }
        return result;
    }

    @Override
    public CartResponse removeFromCart(Long userId, Long cartItemId) {
        return cartService.removeFromCart(userId, cartItemId);
    }

    @Override
    public CheckoutResponse createCheckout(Long userId) {
        // OrderService.checkout() already: re-validates stock per line item,
        // uses the live product price (not a cached one), computes the total,
        // and creates the matching Razorpay order. It also rejects an empty
        // cart. It does not itself deduplicate rapid repeated checkout calls
        // (each call creates a new Order until payment is verified, at which
        // point the cart is cleared) - true idempotency would need a change
        // inside OrderService and is out of scope for an adapter-only change.
        return orderService.checkout(userId);
    }

    @Override
    public List<OrderResponse> getOrders(Long userId, String baseUrl) {
        return orderService.getOrders(userId, resolveBaseUrl(baseUrl));
    }

    @Override
    public OrderResponse getOrder(Long userId, Long orderId, String baseUrl) {
        return orderService.getOrder(userId, orderId, resolveBaseUrl(baseUrl));
    }

    @Override
    public PaymentVerificationResult verifyPayment(Long userId, VerifyPaymentRequest request, String baseUrl) {
        // OrderService.verifyPayment() does the real work: server-side signature
        // verification against Razorpay, and only marks/returns the order as PAID
        // when that verification succeeds. It throws for a bad/unknown order id or
        // a failed signature check - since the AI Agent calls this adapter directly
        // (not through the HTTP layer's GlobalExceptionHandler), those exceptions are
        // translated into a structured "not verified" result here instead of escaping
        // as raw exceptions.
        try {
            OrderResponse order = orderService.verifyPayment(userId, request, resolveBaseUrl(baseUrl));
            return PaymentVerificationResult.verified(order);
        } catch (ResourceNotFoundException e) {
            return PaymentVerificationResult.failed("Invalid order/payment reference: " + e.getMessage());
        } catch (PaymentException e) {
            return PaymentVerificationResult.failed(e.getMessage());
        }
    }

    private CartItemResponse findOwnedCartItem(Long userId, Long cartItemId) {
        return cartService.getCart(userId).getItems().stream()
                .filter(item -> item.getCartItemId().equals(cartItemId))
                .findFirst()
                .orElseThrow(() -> new ResourceNotFoundException("Cart item not found with id: " + cartItemId));
    }

    private String resolveBaseUrl(String baseUrl) {
        return baseUrl == null ? "" : baseUrl;
    }
}
