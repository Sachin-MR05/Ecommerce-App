path = r"src/main/java/com/ecommerce/order/RazorpayService.java"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_method_start = "    public String createPaymentLink(String razorpayOrderId, long amountInPaise) {"
old_method_end = "    }"

# find and replace the entire createPaymentLink block
start = content.find(old_method_start)
if start == -1:
    print("Method not found")
    exit(1)

end = content.find("\n    }", start) + len("\n    }")
old_block = content[start:end]
print("Old block found:", repr(old_block[:80]))

amp = chr(38)  # & character - avoids PowerShell parsing issues
new_block = (
    "    public String createPaymentLink(String razorpayOrderId, long amountInPaise) {\n"
    "        // Returns a Razorpay hosted payment page URL for the buyer to complete payment.\n"
    "        return \"https://checkout.razorpay.com/v1/checkout.html?key=\" + keyId\n"
    "                + \"" + amp + "order_id=\" + razorpayOrderId;\n"
    "    }"
)

content = content[:start] + new_block + content[end:]
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("createPaymentLink simplified successfully")
