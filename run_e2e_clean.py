import httpx, json, time, hmac, hashlib, psycopg2, sys

AGENT_URL = 'http://localhost:8001/agent/message'
TOOL_URL = 'http://localhost:8080/tools'
HEADERS = {
    'Authorization': 'Bearer dev-token',
    'Content-Type': 'application/json'
}
SESSION_ID = f'session-clean-{int(time.time())}'
USER_ID = '1'
KEY_SECRET = 'jHsoTsOUKWtIeKM0R4meGlq7'

def send_message(message: str) -> dict:
    payload = {
        'sessionId': SESSION_ID,
        'userId': USER_ID,
        'message': message,
        'channel': 'web'
    }
    r = httpx.post(AGENT_URL, headers=HEADERS, json=payload, timeout=60)
    return r.json()

def print_safe(label: str, text: str):
    safe_text = text.encode('ascii', 'replace').decode('ascii')
    print(f'{label}: {safe_text}')

# Reset stock and cart
conn = psycopg2.connect(host='localhost', port=5432, dbname='E-Commerce', user='postgres', password='root')
cur = conn.cursor()
cur.execute('UPDATE products SET stock = 10 WHERE id = 5')
cur.execute('DELETE FROM cart_items WHERE user_id = 1')
conn.commit()
cur.close()
conn.close()

print('=== STARTING CLEAN 4-TURN E2E CONVERSATION ===')
time.sleep(5)

# Turn 1
print_safe('\n[User]', 'buy me a i phone')
r1 = send_message('buy me a i phone')
print_safe('[Agent Status]', r1.get('status'))
print_safe('[Agent Response]', r1.get('message'))

print('Waiting 35 seconds to avoid rate limits...')
time.sleep(35)

# Turn 2
choice = 'the standard iPhone (Product ID 5), quantity 1'
print_safe('\n[User]', choice)
r2 = send_message(choice)
print_safe('[Agent Status]', r2.get('status'))
print_safe('[Agent Response]', r2.get('message'))

print('Waiting 35 seconds to avoid rate limits...')
time.sleep(35)

# Turn 3: Confirm checkout
print_safe('\n[User]', 'Yes, please add to cart, proceed to checkout and create the order.')
r3 = send_message('Yes, please add to cart, proceed to checkout and create the order.')
print_safe('[Agent Status]', r3.get('status'))
print_safe('[Agent Response]', r3.get('message'))

# Extract latest Order ID from DB (this must be the newly created order!)
conn = psycopg2.connect(host='localhost', port=5432, dbname='E-Commerce', user='postgres', password='root')
cur = conn.cursor()
cur.execute('SELECT razorpay_order_id, id FROM orders WHERE user_id = 1 ORDER BY created_at DESC LIMIT 1')
order_row = cur.fetchone()
cur.close()
conn.close()

if not order_row or not order_row[0]:
    print('Order not found in DB')
    sys.exit(1)

razorpay_order_id = order_row[0]
local_order_id = order_row[1]

# Simulate payment page link
payment_link = f'https://checkout.razorpay.com/v1/checkout.html?key=rzp_test_TT9dgvW6FBwmgm&order_id={razorpay_order_id}'
print_safe('\n[Payment Link]', payment_link)

# Simulate successful payment signature verification
payment_id = f'pay_sim_{int(time.time())}'
msg = f'{razorpay_order_id}|{payment_id}'
signature = hmac.new(KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

verify_payload = {
    'context': {'userId': 1},
    'arguments': {
        'razorpayOrderId': razorpay_order_id,
        'razorpayPaymentId': payment_id,
        'razorpaySignature': signature
    }
}
v_res = httpx.post(f'{TOOL_URL}/verify_payment/execute', headers={'Content-Type': 'application/json'}, json=verify_payload, timeout=20)

print('Waiting 35 seconds to avoid rate limits...')
time.sleep(35)

# Turn 4: Payment success message
system_msg = f'[System: Payment verified successfully with Razorpay payment ID {payment_id} and signature {signature}. Order status is PAID.]'
print_safe('\n[User/System]', system_msg)
r4 = send_message(system_msg)
print_safe('[Agent Status]', r4.get('status'))
print_safe('[Agent Response]', r4.get('message'))

print('\n=== E2E CONVERSATION COMPLETED ===')
