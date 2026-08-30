import httpx, json

base = "http://localhost:8080/tools"
h = {"Content-Type": "application/json"}

# Step 1: Clear cart and add 1 iPhone fresh
httpx.post(f"{base}/add_to_cart/execute", headers=h,
           json={"context": {"userId": 1}, "arguments": {"productId": 5, "quantity": 1}})

# Step 2: Create a new Razorpay order
r = httpx.post(f"{base}/create_order/execute", headers=h,
               json={"context": {"userId": 1}, "arguments": {}}, timeout=30)
checkout = r.json()

if not checkout.get("success"):
    print("Checkout failed:", checkout)
    exit(1)

result = checkout["result"]
order_id = result["razorpayOrderId"]
key_id = result["keyId"]
amount = result["amount"]
local_order_id = result["orderId"]

print(f"Razorpay Order: {order_id}")
print(f"Amount (paise): {amount}  = Rs {amount//100}")

# Step 3: Write the real payment HTML page
html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Pay for iPhone - Order #{local_order_id}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 80px auto; text-align: center; }}
    h2 {{ color: #333; }}
    .amount {{ font-size: 2em; color: #1a73e8; font-weight: bold; }}
    .btn {{ background: #528FF0; color: white; border: none; padding: 14px 40px;
            font-size: 16px; border-radius: 6px; cursor: pointer; margin-top: 20px; }}
    .btn:hover {{ background: #3a6fd8; }}
    #status {{ margin-top: 30px; padding: 20px; border-radius: 8px; display: none; }}
    .success {{ background: #e6f4ea; color: #137333; border: 1px solid #34a853; }}
    .error {{ background: #fce8e6; color: #c5221f; border: 1px solid #ea4335; }}
    pre {{ text-align: left; font-size: 12px; background: #f5f5f5; padding: 10px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h2>Complete Your Purchase</h2>
  <p>iPhone x 1</p>
  <div class="amount">Rs {amount//100:,}</div>
  <p>Order ID: <code>{order_id}</code></p>

  <button class="btn" onclick="openRazorpay()">Pay Now with Razorpay</button>

  <div id="status"></div>

  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <script>
    function openRazorpay() {{
      var options = {{
        key: "{key_id}",
        amount: "{amount}",
        currency: "INR",
        name: "Ecommerce App",
        description: "iPhone Purchase - Order #{local_order_id}",
        order_id: "{order_id}",
        handler: function(response) {{
          showStatus("Verifying payment...", "");
          fetch("http://localhost:8080/tools/verify_payment/execute", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{
              context: {{userId: 1}},
              arguments: {{
                razorpayOrderId: response.razorpay_order_id,
                razorpayPaymentId: response.razorpay_payment_id,
                razorpaySignature: response.razorpay_signature
              }}
            }})
          }})
          .then(r => r.json())
          .then(data => {{
            if (data.success && data.result.verified) {{
              showStatus(
                "Payment Successful! Order #" + data.result.order.id + " is PAID.<br>" +
                "<pre>" + JSON.stringify(data.result.order, null, 2) + "</pre>",
                "success"
              );
            }} else {{
              showStatus("Verification failed: " + JSON.stringify(data), "error");
            }}
          }})
          .catch(e => showStatus("Error: " + e, "error"));
        }},
        prefill: {{name: "Test Buyer", email: "test@example.com", contact: "9999999999"}},
        theme: {{color: "#528FF0"}}
      }};
      var rzp = new Razorpay(options);
      rzp.open();
    }}

    function showStatus(msg, type) {{
      var el = document.getElementById("status");
      el.innerHTML = msg;
      el.className = type;
      el.style.display = "block";
    }}
  </script>
</body>
</html>"""

with open("payment_page.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nPayment page written: payment_page.html")
print(f"Open this file in your browser to pay!")
