package com.ecommerce.controller;

import com.ecommerce.dto.CartItemRequest;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.security.CurrentUser;
import com.ecommerce.security.UserPrincipal;
import com.ecommerce.service.CartService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

// Every endpoint here requires a logged-in user (see SecurityConfig) and
// only ever touches that user's own cart.
@RestController
@RequestMapping("/cart")
public class CartController {

    private final CartService cartService;

    public CartController(CartService cartService) {
        this.cartService = cartService;
    }

    // GET /cart  -> items + total
    @GetMapping
    public ResponseEntity<CartResponse> getCart(@CurrentUser UserPrincipal user) {
        return ResponseEntity.ok(cartService.getCart(user.getId()));
    }

    // POST /cart  -> add a product (or bump quantity if already present)
    @PostMapping
    public ResponseEntity<CartResponse> addToCart(@CurrentUser UserPrincipal user,
                                                    @Valid @RequestBody CartItemRequest request) {
        return ResponseEntity.ok(cartService.addToCart(user.getId(), request));
    }

    // DELETE /cart/{id}  -> remove a line item entirely
    @DeleteMapping("/{id}")
    public ResponseEntity<CartResponse> removeFromCart(@CurrentUser UserPrincipal user, @PathVariable Long id) {
        return ResponseEntity.ok(cartService.removeFromCart(user.getId(), id));
    }

    // PUT /cart/{id}/increase
    @PutMapping("/{id}/increase")
    public ResponseEntity<CartResponse> increaseQuantity(@CurrentUser UserPrincipal user, @PathVariable Long id) {
        return ResponseEntity.ok(cartService.increaseQuantity(user.getId(), id));
    }

    // PUT /cart/{id}/decrease
    @PutMapping("/{id}/decrease")
    public ResponseEntity<CartResponse> decreaseQuantity(@CurrentUser UserPrincipal user, @PathVariable Long id) {
        return ResponseEntity.ok(cartService.decreaseQuantity(user.getId(), id));
    }

    // DELETE /cart  -> clear entire cart
    @DeleteMapping
    public ResponseEntity<Void> clearCart(@CurrentUser UserPrincipal user) {
        cartService.clearCart(user.getId());
        return ResponseEntity.noContent().build();
    }
}
