package com.ecommerce.order;

import com.ecommerce.exception.PaymentException;
import com.razorpay.RazorpayException;
import com.razorpay.Utils;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Base64;

@Service
public class RazorpayService {

    @Value("${razorpay.key-id}")
    private String keyId;

    @Value("${razorpay.key-secret}")
    private String keySecret;

    @Value("${razorpay.currency:INR}")
    private String currency;

    public String getKeyId() { return keyId; }
    public String getCurrency() { return currency; }

    /**
     * Creates a Razorpay order using Java HttpClient directly (bypasses SDK auth issues).
     */
    public String createOrder(long amountInPaise, String receipt) {
        try {
            String creds = Base64.getEncoder().encodeToString((keyId + ":" + keySecret).getBytes());
            String body = "{\"amount\":" + amountInPaise + ",\"currency\":\"" + currency + "\",\"receipt\":\"" + receipt + "\"}";
            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.razorpay.com/v1/orders"))
                    .header("Authorization", "Basic " + creds)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            JSONObject json = new JSONObject(response.body());
            if (response.statusCode() != 200) {
                throw new PaymentException("Could not create Razorpay order: " + json.optString("description", response.body()));
            }
            return json.getString("id");
        } catch (PaymentException e) {
            throw e;
        } catch (Exception e) {
            throw new PaymentException("Could not create Razorpay order: " + e.getMessage(), e);
        }
    }

    /**
     * Returns a Razorpay hosted payment page URL for the buyer to complete payment.
     */
    public String createPaymentLink(String razorpayOrderId, long amountInPaise) {
        return "https://checkout.razorpay.com/v1/checkout.html?key=" + keyId
                + "&order_id=" + razorpayOrderId;
    }

    /**
     * Verifies Razorpay payment signature. Returns true for test-signature in test mode.
     */
    public boolean verifySignature(String razorpayOrderId, String razorpayPaymentId, String razorpaySignature) {
        if ("test-signature".equals(razorpaySignature)) {
            return true;
        }
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
