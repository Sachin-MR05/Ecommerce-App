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

@Service
public class CartService {

    private final CartRepository cartRepository;
    private final ProductRepository productRepository;

    public CartService(CartRepository cartRepository, ProductRepository productRepository) {
        this.cartRepository = cartRepository;
        this.productRepository = productRepository;
    }

    public CartResponse getCart() {
        List<CartItemResponse> responses = cartRepository.findAll().stream()
                .map(this::toResponse)
                .toList();
        return new CartResponse(responses);
    }

    public CartResponse addToCart(CartItemRequest request) {
        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Product not found with id: " + request.getProductId()));

        var existing = cartRepository.findByProductId(request.getProductId());

        if (existing.isPresent()) {
            CartItem item = existing.get();
            int newQuantity = item.getQuantity() + request.getQuantity();
            checkStock(product, newQuantity);
            item.setQuantity(newQuantity);
            cartRepository.update(item);
        } else {
            checkStock(product, request.getQuantity());
            CartItem item = new CartItem();
            item.setProductId(request.getProductId());
            item.setQuantity(request.getQuantity());
            cartRepository.save(item);
        }

        return getCart();
    }

    public CartResponse removeFromCart(Long cartItemId) {
        boolean removed = cartRepository.deleteById(cartItemId);
        if (!removed) {
            throw new ResourceNotFoundException("Cart item not found with id: " + cartItemId);
        }
        return getCart();
    }

    public CartResponse increaseQuantity(Long cartItemId) {
        return changeQuantity(cartItemId, 1);
    }

    public CartResponse decreaseQuantity(Long cartItemId) {
        return changeQuantity(cartItemId, -1);
    }

    private CartResponse changeQuantity(Long cartItemId, int delta) {
        CartItem item = cartRepository.findById(cartItemId)
                .orElseThrow(() -> new ResourceNotFoundException("Cart item not found with id: " + cartItemId));

        int newQuantity = item.getQuantity() + delta;

        if (newQuantity <= 0) {
            // dropping to zero (or below) removes the item entirely
            cartRepository.deleteById(cartItemId);
            return getCart();
        }

        if (delta > 0) {
            Product product = productRepository.findById(item.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException(
                            "Product not found with id: " + item.getProductId()));
            checkStock(product, newQuantity);
        }

        item.setQuantity(newQuantity);
        cartRepository.update(item);
        return getCart();
    }

    public void clearCart() {
        cartRepository.clear();
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