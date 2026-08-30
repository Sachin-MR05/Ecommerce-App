import psycopg2

# Read DB credentials from .env
env = {}
with open("ecommerce-backend/.env") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

print("DB_URL:", env.get("DB_URL",""))

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="E-Commerce",
    user=env.get("DB_USERNAME", "postgres"),
    password=env.get("DB_PASSWORD", "sachin")
)
cur = conn.cursor()

# Reset iPhone (id=5) stock to 10
cur.execute("UPDATE products SET stock = 10 WHERE id = 5")
cur.execute("DELETE FROM cart_items WHERE user_id = 1")
conn.commit()

cur.execute("SELECT id, name, stock FROM products WHERE id = 5")
print("iPhone after reset:", cur.fetchone())
cur.execute("SELECT COUNT(*) FROM cart_items WHERE user_id = 1")
print("Cart items for user 1:", cur.fetchone()[0])

cur.close()
conn.close()
print("Done")
