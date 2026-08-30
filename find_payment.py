import httpx, base64, json

key_id = "rzp_test_TT9dgvW6FBwmgm"
key_secret = "jHsoTsOUKWtIeKM0R4meGlq7"
order_id = "order_TVA4l8BwHtw0yO"

creds = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
headers = {"Authorization": f"Basic {creds}"}

# Fetch all payments for this order
r = httpx.get(f"https://api.razorpay.com/v1/orders/{order_id}/payments", headers=headers)
data = r.json()
print(json.dumps(data, indent=2))
