package com.ecommerce.order;

import com.ecommerce.exception.PaymentException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.model.CartItem;
import com.ecommerce.model.Order;
import com.ecommerce.model.OrderItem;
import com.ecommerce.model.OrderStatus;
import com.ecommerce.model.Product;
import com.ecommerce.repository.CartRepository;
import com.ecommerce.repository.OrderRepository;
import com.ecommerce.repository.ProductRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final CartRepository cartRepository;
    private final ProductRepository productRepository;
    private final RazorpayService razorpayService;

    public OrderService(OrderRepository orderRepository, CartRepository cartRepository,
                         ProductRepository productRepository, RazorpayService razorpayService) {
        this.orderRepository = orderRepository;
        this.cartRepository = cartRepository;
        this.productRepository = productRepository;
        this.razorpayService = razorpayService;
    }

    /**
     * Turns the user's current cart into an Order (status = CREATED) and asks
     * Razorpay for a matching order id, ready to hand to the Checkout widget.
     */
    @Transactional
    public CheckoutResponse checkout(Long userId) {
        List<CartItem> cartItems = cartRepository.findByUserId(userId);
        if (cartItems.isEmpty()) {
            throw new PaymentException("Your cart is empty");
        }

        Order order = new Order();
        order.setUserId(userId);
        order.setStatus(OrderStatus.CREATED);

        double total = 0;
        for (CartItem cartItem : cartItems) {
            Product product = productRepository.findById(cartItem.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "Product not found with id: " + cartItem.getProductId()));

            if (cartItem.getQuantity() > product.getStock()) {
                throw new PaymentException(
                        "Only " + product.getStock() + " unit(s) of '" + product.getName() + "' left in stock");
            }

            double lineTotal = product.getPrice() * cartItem.getQuantity();
            total += lineTotal;

            order.addItem(new OrderItem(
                    product.getId(),
                    product.getName(),
                    product.getImage(),
                    product.getPrice(),
                    cartItem.getQuantity()
            ));
        }

        order.setTotalAmount(total);
        Order saved = orderRepository.save(order);

        long amountInPaise = Math.round(total * 100);
        String razorpayOrderId = razorpayService.createOrder(amountInPaise, "order_rcpt_" + saved.getId());

        saved.setRazorpayOrderId(razorpayOrderId);
        orderRepository.save(saved);

        return new CheckoutResponse(saved.getId(), razorpayOrderId, amountInPaise,
                razorpayService.getCurrency(), razorpayService.getKeyId());
    }

    /**
     * Verifies the payment Razorpay's Checkout widget reports back, and if
     * genuine: marks the order PAID, decrements stock, and empties the cart.
     */
    @Transactional
    public OrderResponse verifyPayment(Long userId, VerifyPaymentRequest request, String baseUrl) {
        Order order = orderRepository.findByRazorpayOrderId(request.getRazorpayOrderId())
                .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        if (!order.getUserId().equals(userId)) {
            throw new ResourceNotFoundException("Order not found");
        }

        boolean valid = razorpayService.verifySignature(
                request.getRazorpayOrderId(), request.getRazorpayPaymentId(), request.getRazorpaySignature());

        if (!valid) {
            order.setStatus(OrderStatus.FAILED);
            orderRepository.save(order);
            throw new PaymentException("Payment verification failed - please try again");
        }

        order.setStatus(OrderStatus.PAID);
        order.setRazorpayPaymentId(request.getRazorpayPaymentId());
        order.setRazorpaySignature(request.getRazorpaySignature());

        for (OrderItem item : order.getItems()) {
            productRepository.findById(item.getProductId()).ifPresent(product -> {
                int remaining = Math.max(0, product.getStock() - item.getQuantity());
                product.setStock(remaining);
                productRepository.save(product);
            });
        }

        Order saved = orderRepository.save(order);
        cartRepository.deleteByUserId(userId);

        return OrderResponse.fromEntity(saved, baseUrl);
    }

    public List<OrderResponse> getOrders(Long userId, String baseUrl) {
        return orderRepository.findByUserIdOrderByCreatedAtDesc(userId).stream()
                .map(order -> OrderResponse.fromEntity(order, baseUrl))
                .toList();
    }

    public OrderResponse getOrder(Long userId, Long orderId, String baseUrl) {
        Order order = orderRepository.findByIdAndUserId(orderId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found with id: " + orderId));
        return OrderResponse.fromEntity(order, baseUrl);
    }
}
