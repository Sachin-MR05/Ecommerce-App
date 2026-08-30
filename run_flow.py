import httpx, json, time, hmac, hashlib, psycopg2

AGENT_URL = 'http://localhost:8001/agent/message'
TOOL_URL = 'http://localhost:8080/tools'
HEADERS = {
    'Authorization': 'Bearer dev-token',
    'Content-Type': 'application/json'
}
SESSION_ID = f'session-{int(time.time())}'
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

print(f'=== Starting E2E Purchase Flow for Session {SESSION_ID} ===')

# Turn 1: Initial intent
print('\n>>> Sending: \'buy me a i phone\'')
r1 = send_message('buy me a i phone')
print('Status:', r1.get('status'))
print('Agent Response:', r1.get('message'))

# Check if agent asks for model / quantity
if r1.get('status') == 'WAITING_FOR_INPUT':
    print('\n>>> Sending product choice: \'the standard iPhone (Product ID 5), quantity 1\'')
    r2 = send_message('the standard iPhone (Product ID 5), quantity 1')
    print('Status:', r2.get('status'))
    print('Agent Response:', r2.get('message'))
else:
    r2 = r1

# Check if agent is waiting for user confirmation with order details
current_status = r2.get('status')
agent_response = r2.get('message') or ''

if current_status == 'WAITING_FOR_USER' or 'checkout' in agent_response.lower() or 'confirm' in agent_response.lower() or 'cart' in agent_response.lower():
    print('\n>>> Confirming purchase and checking out...')
    r3 = send_message('Yes, confirm checkout and create order.')
    print('Status:', r3.get('status'))
    print('Agent Response:', r3.get('message'))

# Extract Razorpay Order ID from the response or database
conn = psycopg2.connect(host='localhost', port=5432, dbname='E-Commerce', user='postgres', password='root')
cur = conn.cursor()
cur.execute('SELECT razorpay_order_id, id FROM orders WHERE user_id = 1 ORDER BY created_at DESC LIMIT 1')
order_row = cur.fetchone()
cur.close()
conn.close()

if not order_row or not order_row[0]:
    print('Could not retrieve Razorpay Order ID from DB')
    exit(1)

razorpay_order_id = order_row[0]
local_order_id = order_row[1]
print(f'\nOrder created: local ID #{local_order_id}, Razorpay Order ID: {razorpay_order_id}')

# Simulate payment page link
payment_link = f'https://checkout.razorpay.com/v1/checkout.html?key=rzp_test_TT9dgvW6FBwmgm&order_id={razorpay_order_id}'
print(f'Generated Payment Link: {payment_link}')

# Let\'s simulate successful payment captured on Razorpay
payment_id = f'pay_sim_{int(time.time())}'
msg = f'{razorpay_order_id}|{payment_id}'
signature = hmac.new(KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

print(f'\n>>> Simulating payment success for Payment ID: {payment_id}')
verify_payload = {
    'context': {'userId': 1},
    'arguments': {
        'razorpayOrderId': razorpay_order_id,
        'razorpayPaymentId': payment_id,
        'razorpaySignature': signature
    }
}
v_res = httpx.post(f'{TOOL_URL}/verify_payment/execute', headers={'Content-Type': 'application/json'}, json=verify_payload, timeout=20)
print('Verification response:', v_res.json())

# Send the payment confirmation back to the agent
system_msg = f'[System: Payment verified successfully with Razorpay payment ID {payment_id} and signature {signature}. Order status is PAID.]'
print(f'\n>>> Sending payment confirmation message to agent: \'{system_msg}\'')
r4 = send_message(system_msg)
print('Status:', r4.get('status'))
print('Agent Response:', r4.get('message'))

print('\n=== E2E Purchase Flow Finished ===')
