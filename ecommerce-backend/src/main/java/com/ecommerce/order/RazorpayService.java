package com.ecommerce.order;

import com.ecommerce.exception.PaymentException;
import com.razorpay.RazorpayClient;
import com.razorpay.RazorpayException;
import com.razorpay.Utils;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class RazorpayService {

    @Value("${razorpay.key-id}")
    private String keyId;

    @Value("${razorpay.key-secret}")
    private String keySecret;

    @Value("${razorpay.currency:INR}")
    private String currency;

    public String getKeyId() {
        return keyId;
    }

    public String getCurrency() {
        return currency;
    }

    /**
     * Creates an order on Razorpay's side and returns its id (razorpay_order_id).
     * amountInPaise = rupees * 100 (Razorpay always works in the smallest currency unit).
     */
    public String createOrder(long amountInPaise, String receipt) {
        try {
            RazorpayClient client = new RazorpayClient(keyId, keySecret);

            JSONObject orderRequest = new JSONObject();
            orderRequest.put("amount", amountInPaise);
            orderRequest.put("currency", currency);
            orderRequest.put("receipt", receipt);

            com.razorpay.Order razorpayOrder = client.orders.create(orderRequest);
            return razorpayOrder.get("id");
        } catch (RazorpayException e) {
            throw new PaymentException("Could not create Razorpay order: " + e.getMessage(), e);
        }
    }

    /**
     * Verifies the signature Razorpay sends back after a successful payment,
     * proving the payment actually happened and wasn't forged client-side.
     */
    public boolean verifySignature(String razorpayOrderId, String razorpayPaymentId, String razorpaySignature) {
        try {
            JSONObject options = new JSONObject();
            options.put("razorpay_order_id", razorpayOrderId);
            options.put("razorpay_payment_id", razorpayPaymentId);
            options.put("razorpay_signature", razorpaySignature);
            return Utils.verifyPaymentSignature(options, keySecret);
        } catch (RazorpayException e) {
            return false;
        }
    }
}
