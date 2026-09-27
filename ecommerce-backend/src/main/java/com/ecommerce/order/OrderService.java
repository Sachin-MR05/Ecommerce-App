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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final CartRepository cartRepository;
    private final ProductRepository productRepository;
    private final RazorpayService razorpayService;
    private final TransactionTemplate transactionTemplate;

    @Value("${ecommerce.order.timeout-minutes:15}")
    private int orderTimeoutMinutes = 15;

    public OrderService(OrderRepository orderRepository, CartRepository cartRepository,
                         ProductRepository productRepository, RazorpayService razorpayService,
                         PlatformTransactionManager transactionManager) {
        this.orderRepository = orderRepository;
        this.cartRepository = cartRepository;
        this.productRepository = productRepository;
        this.razorpayService = razorpayService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    /**
     * Turns the user's current cart into an Order (status = CREATED) and asks
     * Razorpay for a matching order id, ready to hand to the Checkout widget.
     * Product inventory is reserved with row locks.
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
            Product product = productRepository.findByIdWithLock(cartItem.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "Product not found with id: " + cartItem.getProductId()));

            if (cartItem.getQuantity() > product.getStock()) {
                throw new PaymentException(
                        "Only " + product.getStock() + " unit(s) of '" + product.getName() + "' left in stock");
            }

            // Thread-safe stock reservation with row lock
            int remainingStock = product.getStock() - cartItem.getQuantity();
            product.setStock(remainingStock);
            productRepository.save(product);

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
        cartRepository.deleteByUserId(userId);

        String paymentLink = razorpayService.createPaymentLink(razorpayOrderId, amountInPaise);
        return new CheckoutResponse(saved.getId(), razorpayOrderId, amountInPaise,
                razorpayService.getCurrency(), razorpayService.getKeyId(), paymentLink);
    }

    /**
     * Cancels an order and releases reserved stock using pessimistic write locks.
     * Returns true if cancelled, false if already in a terminal state.
     */
    @Transactional
    public boolean cancelOrderAndReleaseStock(Long orderId) {
        Optional<Order> orderOpt = orderRepository.findByIdWithLock(orderId);
        if (orderOpt.isEmpty()) {
            return false;
        }
        Order order = orderOpt.get();
        if (order.getStatus() != OrderStatus.CREATED) {
            return false;
        }

        order.setStatus(OrderStatus.CANCELLED);
        for (OrderItem item : order.getItems()) {
            productRepository.findByIdWithLock(item.getProductId()).ifPresent(product -> {
                product.setStock(product.getStock() + item.getQuantity());
                productRepository.save(product);
            });
        }
        orderRepository.save(order);
        log.info("Order {} cancelled due to checkout timeout; stock restored.", order.getId());
        return true;
    }

    /**
     * Periodic background task to sweep and release abandoned checkouts.
     * Runs every minute.
     */
    @Scheduled(fixedRate = 60000)
    public void cancelExpiredOrders() {
        LocalDateTime cutoff = LocalDateTime.now().minusMinutes(orderTimeoutMinutes);
        List<Order> expiredOrders = orderRepository.findByStatusAndCreatedAtBefore(OrderStatus.CREATED, cutoff);
        for (Order order : expiredOrders) {
            try {
                transactionTemplate.execute(status -> {
                    cancelOrderAndReleaseStock(order.getId());
                    return null;
                });
            } catch (Exception e) {
                log.error("Failed to cancel expired order id: {}", order.getId(), e);
            }
        }
    }

    /**
     * Verifies the payment Razorpay's Checkout widget reports back, and if genuine:
     * marks the order PAID and records the payment IDs.
     * If invalid: marks FAILED and restores reserved stock.
     */
    @Transactional(noRollbackFor = PaymentException.class)
    public OrderResponse verifyPayment(Long userId, VerifyPaymentRequest request, String baseUrl) {
        Order order = orderRepository.findByRazorpayOrderIdWithLock(request.getRazorpayOrderId())
                .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        // Idempotency: if already marked PAID, return existing order immediately
        if (order.getStatus() == OrderStatus.PAID) {
            return OrderResponse.fromEntity(order, baseUrl);
        }

        if (order.getStatus() == OrderStatus.CANCELLED) {
            throw new PaymentException("This order has expired and was cancelled. Reserved items have been released.");
        }

        // Lazy timeout check: if order passed the cutoff before scheduled job ran
        if (order.getStatus() == OrderStatus.CREATED && order.getCreatedAt() != null
                && order.getCreatedAt().isBefore(LocalDateTime.now().minusMinutes(orderTimeoutMinutes))) {
            order.setStatus(OrderStatus.CANCELLED);
            for (OrderItem item : order.getItems()) {
                productRepository.findByIdWithLock(item.getProductId()).ifPresent(product -> {
                    product.setStock(product.getStock() + item.getQuantity());
                    productRepository.save(product);
                });
            }
            orderRepository.save(order);
            log.info("Order {} cancelled due to lazy checkout timeout; stock restored.", order.getId());
            throw new PaymentException("Checkout session expired. Reserved items have been released.");
        }

        boolean valid = razorpayService.verifySignature(
                request.getRazorpayOrderId(), request.getRazorpayPaymentId(), request.getRazorpaySignature());

        if (!valid) {
            order.setStatus(OrderStatus.FAILED);
            // Restore stock on payment verification failure
            for (OrderItem item : order.getItems()) {
                productRepository.findByIdWithLock(item.getProductId()).ifPresent(product -> {
                    product.setStock(product.getStock() + item.getQuantity());
                    productRepository.save(product);
                });
            }
            orderRepository.save(order);
            throw new PaymentException("Payment verification failed - please try again");
        }

        order.setStatus(OrderStatus.PAID);
        order.setRazorpayPaymentId(request.getRazorpayPaymentId());
        order.setRazorpaySignature(request.getRazorpaySignature());

        // Stock was already reserved during checkout, so no redundant second decrement needed here.

        Order saved = orderRepository.save(order);
        cartRepository.deleteByUserId(userId);

        return OrderResponse.fromEntity(saved, baseUrl);
    }

    @Transactional
    public OrderResponse cancelOrder(Long userId, Long orderId, String baseUrl) {
        Order order = orderRepository.findByIdWithLock(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found with id: " + orderId));
        if (!order.getUserId().equals(userId)) {
            throw new PaymentException("You are not authorized to cancel this order");
        }
        if (order.getStatus() != OrderStatus.CREATED) {
            throw new PaymentException("Order cannot be cancelled in status: " + order.getStatus());
        }
        cancelOrderAndReleaseStock(order.getId());
        Order cancelledOrder = orderRepository.findById(orderId).orElse(order);
        return OrderResponse.fromEntity(cancelledOrder, baseUrl);
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
