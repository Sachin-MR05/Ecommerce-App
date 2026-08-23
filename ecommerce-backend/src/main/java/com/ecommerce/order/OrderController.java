package com.ecommerce.order;

import com.ecommerce.security.CurrentUser;
import com.ecommerce.security.UserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

// Every endpoint here requires a logged-in user (see SecurityConfig) and
// only ever touches that user's own orders.
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    // POST /orders/checkout  -> creates a Razorpay order from the current cart
    @PostMapping("/checkout")
    public ResponseEntity<CheckoutResponse> checkout(@CurrentUser UserPrincipal user) {
        return ResponseEntity.ok(orderService.checkout(user.getId()));
    }

    // POST /orders/verify-payment  -> confirms payment success after the Razorpay widget closes
    @PostMapping("/verify-payment")
    public ResponseEntity<OrderResponse> verifyPayment(@CurrentUser UserPrincipal user,
                                                         @Valid @RequestBody VerifyPaymentRequest request,
                                                         HttpServletRequest httpRequest) {
        return ResponseEntity.ok(orderService.verifyPayment(user.getId(), request, getBaseUrl(httpRequest)));
    }

    // GET /orders  -> the logged-in user's order history
    @GetMapping
    public ResponseEntity<List<OrderResponse>> getOrders(@CurrentUser UserPrincipal user, HttpServletRequest request) {
        return ResponseEntity.ok(orderService.getOrders(user.getId(), getBaseUrl(request)));
    }

    // GET /orders/{id}  -> a single order's detail
    @GetMapping("/{id}")
    public ResponseEntity<OrderResponse> getOrder(@CurrentUser UserPrincipal user, @PathVariable Long id,
                                                    HttpServletRequest request) {
        return ResponseEntity.ok(orderService.getOrder(user.getId(), id, getBaseUrl(request)));
    }

    private String getBaseUrl(HttpServletRequest request) {
        return request.getScheme() + "://" + request.getServerName() + ":" + request.getServerPort();
    }
}
