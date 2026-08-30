import hmac, hashlib, httpx, json

key_secret = "jHsoTsOUKWtIeKM0R4meGlq7"
order_id = "order_TVA4l8BwHtw0yO"
payment_id = "pay_TVA6UqzBqHBcc5"

# Generate the correct Razorpay signature
msg = f"{order_id}|{payment_id}"
signature = hmac.new(key_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
print(f"Generated signature: {signature}")

# Call verify_payment with the real signature
r = httpx.post("http://localhost:8080/tools/verify_payment/execute",
    headers={"Content-Type": "application/json"},
    json={"context": {"userId": 1}, "arguments": {
        "razorpayOrderId": order_id,
        "razorpayPaymentId": payment_id,
        "razorpaySignature": signature
    }})
result = r.json()
print(json.dumps(result, indent=2))
