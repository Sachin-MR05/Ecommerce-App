package com.ecommerce.repository;

import com.ecommerce.model.CartItem;
import com.ecommerce.util.JsonUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class CartRepository {

    @Value("${app.data.cart-file}")
    private String cartFilePath;

    private final JsonUtil jsonUtil;

    public CartRepository(JsonUtil jsonUtil) {
        this.jsonUtil = jsonUtil;
    }

    public List<CartItem> findAll() {
        return jsonUtil.readList(cartFilePath, CartItem.class);
    }

    public Optional<CartItem> findById(Long id) {
        return findAll().stream()
                .filter(c -> c.getId().equals(id))
                .findFirst();
    }

    public Optional<CartItem> findByProductId(Long productId) {
        return findAll().stream()
                .filter(c -> c.getProductId().equals(productId))
                .findFirst();
    }

    public CartItem save(CartItem item) {
        List<CartItem> items = findAll();

        long nextId = items.stream()
                .mapToLong(CartItem::getId)
                .max()
                .orElse(0L) + 1;

        item.setId(nextId);
        items.add(item);
        jsonUtil.writeList(cartFilePath, items);
        return item;
    }

    public CartItem update(CartItem updatedItem) {
        List<CartItem> items = findAll();

        for (int i = 0; i < items.size(); i++) {
            if (items.get(i).getId().equals(updatedItem.getId())) {
                items.set(i, updatedItem);
                jsonUtil.writeList(cartFilePath, items);
                return updatedItem;
            }
        }

        return null;
    }

    public boolean deleteById(Long id) {
        List<CartItem> items = findAll();
        boolean removed = items.removeIf(c -> c.getId().equals(id));

        if (removed) {
            jsonUtil.writeList(cartFilePath, items);
        }

        return removed;
    }

    public void clear() {
        jsonUtil.writeList(cartFilePath, new java.util.ArrayList<>());
    }
}