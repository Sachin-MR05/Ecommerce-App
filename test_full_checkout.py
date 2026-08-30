import httpx, json

base = "http://localhost:8080/tools"
h = {"Content-Type": "application/json"}
ctx = {"userId": 1}

# Step 1: Add 1 iPhone to cart
r1 = httpx.post(f"{base}/add_to_cart/execute", headers=h,
                json={"context": ctx, "arguments": {"productId": 5, "quantity": 1}})
cart = r1.json()
print("=== CART ===")
print(json.dumps(cart, indent=2))

if not cart.get("success"):
    print("Cart failed, stopping")
    exit(1)

# Step 2: Checkout - should return paymentLink
r2 = httpx.post(f"{base}/create_order/execute", headers=h,
                json={"context": ctx, "arguments": {}}, timeout=30)
checkout = r2.json()
print("\n=== CHECKOUT ===")
print(json.dumps(checkout, indent=2))

if checkout.get("success"):
    link = checkout.get("result", {}).get("paymentLink")
    print(f"\n*** PAYMENT LINK: {link} ***")
    print("Open this URL in your browser to complete payment!")
