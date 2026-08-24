package com.ecommerce.tools;

import com.ecommerce.exception.InsufficientStockException;
import com.ecommerce.exception.PaymentException;
import com.ecommerce.exception.ResourceNotFoundException;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolResponse;
import com.ecommerce.tools.model.ToolValidationException;

/**
 * Base class for every tool in this layer. Centralizes:
 *  - the exception-to-ToolResponse translation (so every tool returns the
 *    same structured shape for the same class of failure, and no tool has
 *    to duplicate this try/catch)
 *  - the "this operation needs an authenticated user" check shared by the
 *    cart/order/payment tools
 *
 * Concrete tools only implement handle(request): validate their own
 * arguments, delegate to MerchantCommerceAdapter, and return the raw
 * success payload.
 */
public abstract class AbstractAgentTool implements AgentTool {

    @Override
    public final ToolResponse execute(ToolRequest request) {
        try {
            return ToolResponse.success(handle(request));
        } catch (ToolValidationException e) {
            return ToolResponse.failure("VALIDATION_ERROR", e.getMessage());
        } catch (ResourceNotFoundException e) {
            return ToolResponse.failure("NOT_FOUND", e.getMessage());
        } catch (InsufficientStockException e) {
            return ToolResponse.failure("INSUFFICIENT_STOCK", e.getMessage());
        } catch (PaymentException e) {
            return ToolResponse.failure("PAYMENT_ERROR", e.getMessage());
        } catch (Exception e) {
            // Never leak internals (stack traces, SQL, etc.) to the agent/LLM.
            return ToolResponse.failure("INTERNAL_ERROR",
                    "Something went wrong while executing tool '" + getName() + "'");
        }
    }

    /**
     * Validate the request and delegate the actual work to
     * MerchantCommerceAdapter, returning the raw success payload.
     * Let exceptions propagate - execute() above translates them.
     */
    protected abstract Object handle(ToolRequest request);

    /**
     * Cart/order/payment operations are scoped to a specific user. That
     * user id must come from the authenticated session/orchestrator context
     * (ToolRequest.userId), never from the agent's own tool arguments -
     * otherwise the agent could simply pass a different userId and act on
     * someone else's cart or orders.
     */
    protected Long requireUserId(ToolRequest request) {
        Long userId = request.getUserId();
        if (userId == null) {
            throw new ToolValidationException(
                    "This operation requires an authenticated user context, which must be supplied " +
                            "by the calling session/orchestrator - it cannot be provided as a tool argument.");
        }
        return userId;
    }
}
