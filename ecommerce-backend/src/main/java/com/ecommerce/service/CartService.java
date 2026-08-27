package com.ecommerce.service;

import com.ecommerce.dto.CartItemRequest;
import com.ecommerce.dto.CartItemResponse;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.exception.InsufficientStockException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.model.CartItem;
import com.ecommerce.model.Product;
import com.ecommerce.repository.CartRepository;
import com.ecommerce.repository.ProductRepository;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Every method is scoped to the currently logged-in user's id,
 * so each customer only ever sees/modifies their own cart.
 */
@Service
public class CartService {

    private final CartRepository cartRepository;
    private final ProductRepository productRepository;

    public CartService(CartRepository cartRepository, ProductRepository productRepository) {
        this.cartRepository = cartRepository;
        this.productRepository = productRepository;
    }

    public CartResponse getCart(Long userId) {
        List<CartItemResponse> responses = cartRepository.findByUserId(userId).stream()
                .map(this::toResponse)
                .toList();
        return new CartResponse(responses);
    }

    public CartResponse addToCart(Long userId, CartItemRequest request) {
        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Product not found with id: " + request.getProductId()));

        var existing = cartRepository.findByUserIdAndProductId(userId, request.getProductId());

        if (existing.isPresent()) {
            CartItem item = existing.get();
            int newQuantity = item.getQuantity() + request.getQuantity();
            checkStock(product, newQuantity);
            item.setQuantity(newQuantity);
            cartRepository.save(item);
        } else {
            checkStock(product, request.getQuantity());
            CartItem item = new CartItem();
            item.setUserId(userId);
            item.setProductId(request.getProductId());
            item.setQuantity(request.getQuantity());
            cartRepository.save(item);
        }

        return getCart(userId);
    }

    public CartResponse removeFromCart(Long userId, Long cartItemId) {
        CartItem item = getOwnedItem(userId, cartItemId);
        cartRepository.deleteById(item.getId());
        return getCart(userId);
    }

    public CartResponse increaseQuantity(Long userId, Long cartItemId) {
        return changeQuantity(userId, cartItemId, 1);
    }

    public CartResponse decreaseQuantity(Long userId, Long cartItemId) {
        return changeQuantity(userId, cartItemId, -1);
    }

    private CartResponse changeQuantity(Long userId, Long cartItemId, int delta) {
        CartItem item = getOwnedItem(userId, cartItemId);

        int newQuantity = item.getQuantity() + delta;

        if (newQuantity <= 0) {
            // dropping to zero (or below) removes the item entirely
            cartRepository.deleteById(item.getId());
            return getCart(userId);
        }

        if (delta > 0) {
            Product product = productRepository.findById(item.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "Product not found with id: " + item.getProductId()));
            checkStock(product, newQuantity);
        }

        item.setQuantity(newQuantity);
        cartRepository.save(item);
        return getCart(userId);
    }

    public void clearCart(Long userId) {
        cartRepository.deleteByUserId(userId);
    }

    // makes sure a customer can't touch another customer's cart item by guessing its id
    private CartItem getOwnedItem(Long userId, Long cartItemId) {
        CartItem item = cartRepository.findById(cartItemId)
                .orElseThrow(() -> new ResourceNotFoundException("Cart item not found with id: " + cartItemId));
        if (!item.getUserId().equals(userId)) {
            throw new ResourceNotFoundException("Cart item not found with id: " + cartItemId);
        }
        return item;
    }

    private void checkStock(Product product, int requestedQuantity) {
        if (requestedQuantity > product.getStock()) {
            throw new InsufficientStockException(
                    "Only " + product.getStock() + " unit(s) of '" + product.getName() + "' available");
        }
    }

    private CartItemResponse toResponse(CartItem item) {
        Product product = productRepository.findById(item.getProductId())
                .orElse(null);

        String name = product != null ? product.getName() : "Unknown product";
        String image = product != null ? product.getImage() : null;
        double price = product != null ? product.getPrice() : 0.0;

        return new CartItemResponse(item.getId(), item.getProductId(), name, image, price, item.getQuantity());
    }
}
