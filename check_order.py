import psycopg2

env = {}
with open("ecommerce-backend/.env") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

conn = psycopg2.connect(host="localhost", port=5432, dbname="E-Commerce",
    user=env.get("DB_USERNAME","postgres"), password=env.get("DB_PASSWORD","sachin"))
cur = conn.cursor()

cur.execute("""
    SELECT o.id, o.status, o.total_amount, o.razorpay_order_id, o.razorpay_payment_id, o.created_at
    FROM orders o
    WHERE o.user_id = 1
    ORDER BY o.created_at DESC
    LIMIT 5
""")
rows = cur.fetchall()
print("=== RECENT ORDERS FOR USER 1 ===")
for r in rows:
    print(f"  Order #{r[0]} | Status: {r[1]} | Amount: Rs {r[2]:,.0f} | Razorpay: {r[3]} | PaymentID: {r[4]}")

cur.close()
conn.close()
