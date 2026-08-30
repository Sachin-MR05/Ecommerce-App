path = r"src/test/java/com/ecommerce/tools/product/SearchProductsEndToEndTest.java"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = 'return new CheckoutResponse(100L, "rzp_order_abc123", 29900L, "INR", "rzp_test_key");'
new = 'return new CheckoutResponse(100L, "rzp_order_abc123", 29900L, "INR", "rzp_test_key", null);'

if old in content:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Test fixed")
else:
    print("Pattern not found")
    idx = content.find("CheckoutResponse(")
    print(repr(content[max(0,idx-5):idx+150]))
