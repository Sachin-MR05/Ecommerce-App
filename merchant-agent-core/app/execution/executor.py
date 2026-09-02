from __future__ import annotations







import logging



from typing import Optional







from app.agent.agent_state import AgentState



from audit.audit_event import AuditEventType



from audit.audit_service import AuditService



from failure_handling.failure_handler import FailureHandler



from failure_handling.idempotency import DuplicateOperationInProgressError, IdempotencyStatus



from app.planning.decision import Decision



from app.tools.tool_client import ToolClient, ToolClientError



from app.tools.tool_schema import ToolCallResult, ToolDefinition







logger = logging.getLogger(__name__)


def _clear_cart_for_user(user_id: Any) -> None:
    try:
        import psycopg
        try:
            uid = int(user_id) if user_id else 1
        except (TypeError, ValueError):
            uid = 1
        with psycopg.connect("postgresql://postgres:root@localhost:5432/E-Commerce", connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cart_items WHERE user_id = %s", (uid,))
                conn.commit()
                logger.info("Cleared cart_items for user_id=%s before add_to_cart", uid)
    except Exception as exc:
        logger.warning("Could not auto-clear cart for user_id=%s: %s", user_id, exc)











class ExecutorError(Exception):



    """A tool call could not be executed as decided."""











class UnknownToolError(ExecutorError):



    """The planner selected a tool that isn't in the request's available tool definitions."""











class InvalidToolArgumentsError(ExecutorError):



    """The supplied arguments don't satisfy the tool's declared input schema."""











# Tool names whose execution represents a payment/order operation and



# therefore get idempotency protection + PAYMENT_*/ORDER_CREATED audit



# events. Kept here (rather than in tool_schema.py's KNOWN_TOOL_NAMES,



# which is documentation-only) because this is Failure Handling/Audit



# Service policy, not a wire contract.



PAYMENT_TOOL_NAMES: frozenset[str] = frozenset({"verify_payment"})



ORDER_TOOL_NAMES: frozenset[str] = frozenset({"create_order"})



IDEMPOTENCY_PROTECTED_TOOLS: frozenset[str] = PAYMENT_TOOL_NAMES | ORDER_TOOL_NAMES







# Best-effort, response-shape-agnostic lookup for a transaction/order



# identifier in a tool's result data, for audit traceability only. Never



# required - absence just means the audit trail for that event has no



# transaction_id.



_TRANSACTION_ID_KEYS: tuple[str, ...] = ("transactionId", "orderId", "id")











class Executor:



    """Executes a validated TOOL_CALL Decision against the Java Tool Layer



    via ToolClient, and records the outcome on the AgentState.







    Never decides which tool to use - that belongs to the planner/LLM. This



    class only validates that the chosen tool/arguments are legitimate,



    delegates, and captures the result.







    failure_handler and audit_service are optional (default to no



    integration) so existing callers/tests that construct



    `Executor(tool_client)` keep working unchanged. When supplied, the



    Executor never lets either one change control flow beyond what's



    documented below - failure_handler only classifies/decides recovery



    and protects against duplicate payment/order execution; audit_service



    only records what happened.



    """







    def __init__(



        self,



        tool_client: ToolClient,



        failure_handler: Optional[FailureHandler] = None,



        audit_service: Optional[AuditService] = None,



    ):



        self._tool_client = tool_client



        self._failure_handler = failure_handler



        self._audit_service = audit_service







    def execute(self, decision: Decision, state: AgentState) -> ToolCallResult:



        # Normalize snake_case arguments to camelCase for Java compatibility



        normalized_args = {}



        for k, v in decision.arguments.items():



            if "_" in k:



                parts = k.split("_")



                camel_k = parts[0] + "".join(p.capitalize() for p in parts[1:])



                normalized_args[camel_k] = v



            else:



                normalized_args[k] = v



        



        # Resilient injection of selected product info if missing from model's decision



        if "productId" not in normalized_args and state.selected_product_id is not None:



            normalized_args["productId"] = state.selected_product_id



        if "quantity" not in normalized_args and state.selected_quantity is not None:



            normalized_args["quantity"] = state.selected_quantity







        decision.arguments = normalized_args







        tool_definition = self._require_known_tool(decision.tool_name, state.available_tools)



        self._validate_arguments(tool_definition, decision.arguments)







        state.record_tool_call(decision.tool_name, decision.arguments)



        logger.info("Executing tool '%s' for session %s", decision.tool_name, state.session_id)







        request_id = state.request_id or state.session_id



        tool_name = decision.tool_name







        idempotency_key: Optional[str] = None



        if self._failure_handler is not None and tool_name in IDEMPOTENCY_PROTECTED_TOOLS:



            cached = self._check_idempotency(tool_name, decision.arguments, request_id, state)



            if cached is not None:



                return cached



            idempotency_key = self._failure_handler.idempotency_key_for(tool_name, None, decision.arguments)







        self._audit_tool_call_started(tool_name, decision.arguments, request_id)







        if tool_name == "add_to_cart":
            _clear_cart_for_user(state.user_id)

        try:



            result = self._tool_client.execute_tool(tool_name, decision.arguments, user_id=state.user_id)



        except ToolClientError as exc:



            logger.error("Tool '%s' execution failed: %s", tool_name, exc)



            state.record_tool_error(str(exc))



            self._handle_transport_failure(exc, tool_name, request_id, idempotency_key)



            raise ExecutorError(str(exc)) from exc







        state.record_tool_result(result)



        transaction_id = _extract_transaction_id(result.data)



        self._audit_tool_outcome(tool_name, result, request_id, transaction_id)
        
        self._finish_idempotency(idempotency_key, result)

        if tool_name == "create_order" and result.success and result.data:
            # Intercept and rewrite payment link to point to React guest checkout (http://localhost:3000/checkout)
            key_id = result.data.get("keyId")
            razorpay_order_id = result.data.get("razorpayOrderId")
            amount = result.data.get("amount")
            currency = result.data.get("currency")
            
            frontend_url = f"http://localhost:3000/checkout?key={key_id}&order_id={razorpay_order_id}&amount={amount}&currency={currency}"
            
            result.data["paymentLink"] = frontend_url
            if hasattr(result, "result") and isinstance(result.result, dict):
                result.result["paymentLink"] = frontend_url

            try:
                self._update_payment_page(result.data)
            except Exception as exc:
                logger.error("Failed to update payment page: %s", exc)







        return result







    def _update_payment_page(self, result_data: dict) -> None:



        order_id = result_data.get("orderId")



        razorpay_order_id = result_data.get("razorpayOrderId")



        amount_paise = result_data.get("amount")



        currency = result_data.get("currency")



        key_id = result_data.get("keyId")



        



        amount_inr = amount_paise / 100.0



        



        import psycopg2



        try:



            conn = psycopg2.connect(host="localhost", port=5432, dbname="E-Commerce", user="postgres", password="root")



            cur = conn.cursor()



            cur.execute("SELECT product_name, quantity FROM order_items WHERE order_id = %s", (order_id,))



            items = cur.fetchall()



            cur.close()



            conn.close()



            items_desc = ", ".join(f"{name} x {qty}" for name, qty in items)



        except Exception as exc:



            import logging



            logger = logging.getLogger(__name__)



            logger.error("Could not fetch order items from DB: %s", exc)



            items_desc = "Order Items"







        html_content = f"""<!DOCTYPE html>



<html>



<head>



  <title>Pay for Order #{order_id}</title>



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



  <p>{items_desc}</p>



  <div class="amount">Rs {amount_inr:,.2f}</div>



  <p>Order ID: <code>{razorpay_order_id}</code></p>







  <button class="btn" onclick="openRazorpay()">Pay Now with Razorpay</button>







  <div id="status"></div>







  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>



  <script>



    function openRazorpay() {{



      var options = {{



        key: "{key_id}",



        amount: "{amount_paise}",



        currency: "{currency}",



        name: "Ecommerce App",



        description: "{items_desc} - Order #{order_id}",



        order_id: "{razorpay_order_id}",



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



</html>



"""



        import os



        # Path to root relative to execution context



        # Since uvicorn runs in merchant-agent-core/ or root, let's write to root



        root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



        page_path = os.path.join(root_path, "payment_page.html")



        with open(page_path, "w", encoding="utf-8") as f:



            f.write(html_content)











    # ------------------------------------------------------------------



    # Idempotency



    # ------------------------------------------------------------------







    def _check_idempotency(



        self, tool_name: str, arguments: dict, request_id: str, state: AgentState



    ) -> Optional[ToolCallResult]:



        """Returns a cached result if this exact operation already ran to



        completion, so the caller returns early without re-invoking the



        tool. Raises ExecutorError if the same operation is already



        in-flight (concurrent duplicate)."""



        assert self._failure_handler is not None



        key = self._failure_handler.idempotency_key_for(tool_name, None, arguments)



        try:



            record = self._failure_handler.begin_protected_operation(key, None, tool_name)



        except DuplicateOperationInProgressError as exc:



            logger.warning("Duplicate in-flight operation for tool '%s': %s", tool_name, exc)



            raise ExecutorError(str(exc)) from exc







        if record.status == IdempotencyStatus.IN_PROGRESS:



            return None  # first time seeing this key - proceed normally







        logger.info(



            "Idempotent replay for tool '%s' (status=%s) - returning existing result instead of re-executing",



            tool_name,



            record.status.value,



        )



        if self._audit_service is not None:



            event_type = AuditEventType.TOOL_SUCCESS if record.status == IdempotencyStatus.SUCCEEDED else AuditEventType.TOOL_FAILURE



            self._audit_service.record_event(



                event_type,



                component="Executor",



                operation=tool_name,



                status=record.status.value,



                request_id=request_id,



                metadata={"idempotent_replay": True},



            )







        if record.status == IdempotencyStatus.SUCCEEDED and record.result is not None:



            # record.result is whatever ToolClient.execute_tool returned for



            # the original call (today, a contracts.tool_response.ToolResponse -



            # duck-type compatible with ToolCallResult's success/data/



            # error_code/error_message surface used throughout this module).



            state.record_tool_result(record.result)



            return record.result







        error_message = record.error or f"Operation '{tool_name}' previously failed"



        state.record_tool_error(error_message)



        raise ExecutorError(error_message)







    def _finish_idempotency(self, idempotency_key: Optional[str], result: ToolCallResult) -> None:



        if idempotency_key is None or self._failure_handler is None:



            return



        if result.success:



            self._failure_handler.complete_protected_operation(idempotency_key, result)



        else:



            self._failure_handler.fail_protected_operation(idempotency_key, result.error_message or "tool reported failure")







    # ------------------------------------------------------------------



    # Failure classification (delegates the decision; never retries here



    # itself - the agent loop/caller acts on the recovery decision)



    # ------------------------------------------------------------------







    def _handle_transport_failure(



        self, exc: ToolClientError, tool_name: str, request_id: str, idempotency_key: Optional[str]



    ) -> None:



        if idempotency_key is not None and self._failure_handler is not None:



            self._failure_handler.fail_protected_operation(idempotency_key, str(exc))







        standard_error = None



        if self._failure_handler is not None:



            recovery = self._failure_handler.handle_tool_client_exception(



                exc, component="Executor", attempt=1, request_id=request_id



            )



            standard_error = recovery.standard_error







        if self._audit_service is not None:



            self._audit_service.record_event(



                AuditEventType.TOOL_FAILURE,



                component="Executor",



                operation=tool_name,



                status="FAILED",



                request_id=request_id,



                error_code=standard_error.error_code if standard_error else None,



                error_message=str(exc),



            )



            if tool_name in PAYMENT_TOOL_NAMES:



                self._audit_service.record_event(



                    AuditEventType.PAYMENT_FAILED,



                    component="Executor",



                    operation=tool_name,



                    status="FAILED",



                    request_id=request_id,



                    error_message=str(exc),



                )







    # ------------------------------------------------------------------



    # Audit helpers



    # ------------------------------------------------------------------







    def _audit_tool_call_started(self, tool_name: str, arguments: dict, request_id: str) -> None:



        if self._audit_service is None:



            return



        self._audit_service.record_event(



            AuditEventType.TOOL_CALL,



            component="Executor",



            operation=tool_name,



            status="STARTED",



            request_id=request_id,



        )



        if tool_name in PAYMENT_TOOL_NAMES:



            self._audit_service.record_event(



                AuditEventType.PAYMENT_INITIATED,



                component="Executor",



                operation=tool_name,



                status="STARTED",



                request_id=request_id,



            )







    def _audit_tool_outcome(



        self, tool_name: str, result: ToolCallResult, request_id: str, transaction_id: Optional[str]



    ) -> None:



        if self._audit_service is None:



            return







        if result.success:



            self._audit_service.record_event(



                AuditEventType.TOOL_SUCCESS,



                component="Executor",



                operation=tool_name,



                status="SUCCESS",



                request_id=request_id,



                transaction_id=transaction_id,



            )



            if tool_name in PAYMENT_TOOL_NAMES:



                self._audit_service.record_event(



                    AuditEventType.PAYMENT_SUCCESS,



                    component="Executor",



                    operation=tool_name,



                    status="SUCCESS",



                    request_id=request_id,



                    transaction_id=transaction_id,



                )



            if tool_name in ORDER_TOOL_NAMES:



                self._audit_service.record_event(



                    AuditEventType.ORDER_CREATED,



                    component="Executor",



                    operation=tool_name,



                    status="SUCCESS",



                    request_id=request_id,



                    transaction_id=transaction_id,



                )



            return







        error = getattr(result, "error", None)



        recovery_error_code = error.code if error else result.error_code



        recovery_error_message = error.message if error else result.error_message







        if self._failure_handler is not None and error is not None:



            self._failure_handler.handle_tool_error(



                error, component="Executor", attempt=1, transaction_id=transaction_id, request_id=request_id



            )







        self._audit_service.record_event(



            AuditEventType.TOOL_FAILURE,



            component="Executor",



            operation=tool_name,



            status="FAILED",



            request_id=request_id,



            transaction_id=transaction_id,



            error_code=recovery_error_code,



            error_message=recovery_error_message,



        )



        if tool_name in PAYMENT_TOOL_NAMES:



            self._audit_service.record_event(



                AuditEventType.PAYMENT_FAILED,



                component="Executor",



                operation=tool_name,



                status="FAILED",



                request_id=request_id,



                transaction_id=transaction_id,



                error_code=recovery_error_code,



                error_message=recovery_error_message,



            )







    def _require_known_tool(self, tool_name: str, available_tools: list[ToolDefinition]) -> ToolDefinition:



        for tool in available_tools:



            if tool.name == tool_name:



                return tool



        raise UnknownToolError(f"Tool '{tool_name}' is not among the tools available for this request")







    def _validate_arguments(self, tool: ToolDefinition, arguments: dict) -> None:



        required = tool.input_schema.get("required", []) if isinstance(tool.input_schema, dict) else []



        missing = [name for name in required if name not in arguments]



        if missing:



            raise InvalidToolArgumentsError(



                f"Tool '{tool.name}' is missing required argument(s): {', '.join(missing)}"



            )











def _extract_transaction_id(data) -> Optional[str]:



    if not isinstance(data, dict):



        return None



    for key in _TRANSACTION_ID_KEYS:



        if key in data and data[key] is not None:



            return str(data[key])



    return None



