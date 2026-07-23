package com.ecommerce.controller;

import com.ecommerce.dto.CartItemRequest;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.service.CartService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/cart")
public class CartController {

    private final CartService cartService;

    public CartController(CartService cartService) {
        this.cartService = cartService;
    }

    // GET /cart  -> items + total
    @GetMapping
    public ResponseEntity<CartResponse> getCart() {
        return ResponseEntity.ok(cartService.getCart());
    }

    // POST /cart  -> add a product (or bump quantity if already present)
    @PostMapping
    public ResponseEntity<CartResponse> addToCart(@Valid @RequestBody CartItemRequest request) {
        return ResponseEntity.ok(cartService.addToCart(request));
    }

    // DELETE /cart/{id}  -> remove a line item entirely
    @DeleteMapping("/{id}")
    public ResponseEntity<CartResponse> removeFromCart(@PathVariable Long id) {
        return ResponseEntity.ok(cartService.removeFromCart(id));
    }

    // PUT /cart/{id}/increase
    @PutMapping("/{id}/increase")
    public ResponseEntity<CartResponse> increaseQuantity(@PathVariable Long id) {
        return ResponseEntity.ok(cartService.increaseQuantity(id));
    }

    // PUT /cart/{id}/decrease
    @PutMapping("/{id}/decrease")
    public ResponseEntity<CartResponse> decreaseQuantity(@PathVariable Long id) {
        return ResponseEntity.ok(cartService.decreaseQuantity(id));
    }

    // DELETE /cart  -> clear entire cart
    @DeleteMapping
    public ResponseEntity<Void> clearCart() {
        cartService.clearCart();
        return ResponseEntity.noContent().build();
    }
}