import httpx, json

base = "http://localhost:8080/tools"
h = {"Content-Type": "application/json"}

# Add 1 iPhone to cart
r1 = httpx.post(f"{base}/add_to_cart/execute", headers=h,
                json={"context": {"userId": 1}, "arguments": {"productId": 5, "quantity": 1}})
print("Cart:", json.dumps(r1.json(), indent=2))

# Checkout - should now return paymentLink
r2 = httpx.post(f"{base}/create_order/execute", headers=h,
                json={"context": {"userId": 1}, "arguments": {}})
print("Checkout:", json.dumps(r2.json(), indent=2))
