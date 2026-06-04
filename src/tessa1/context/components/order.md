# Order Service - eShopOnWeb

## Overview
The Order Service handles order creation, payment processing, and order management. It orchestrates the checkout process.

---

## Entities

### Order
**Location:** `ApplicationCore/Entities/OrderAggregate/Order.cs`

**Properties:**
- `Id` (int) - Primary key
- `BuyerId` (string) - User identifier
- `OrderDate` (DateTimeOffset) - When order was placed
- `ShipToAddress` (Address) - Shipping destination
- `OrderItems` (List<OrderItem>) - Line items
- `Total()` (decimal) - Calculated total price

### OrderItem
**Properties:**
- `Id` (int)
- `ItemOrdered` (CatalogItemOrdered) - Snapshot of catalog item
- `UnitPrice` (decimal)
- `Units` (int) - Quantity

---

## OrderService

**Location:** `ApplicationCore/Services/OrderService.cs`

### Key Methods

#### CreateOrderAsync
```csharp
Task<Order> CreateOrderAsync(
    string buyerId,
    int deliveryMethodId,
    int basketId,
    Address shippingAddress
);
```

**Process:**
1. Retrieve basket
2. Validate basket items exist in catalog
3. Create order from basket items
4. Call payment service
5. Clear basket
6. Save order to database
7. Return order

**Dependencies:**
- BasketService
- CatalogService (validate items)
- IPaymentService
- CatalogContext (persist order)

---

## Order Creation Flow

```
User → POST /Basket/Checkout
  ↓
BasketController.Checkout(checkoutModel)
  ↓
CreateOrderCommandHandler.Handle(command)
  ↓
OrderService.CreateOrderAsync(buyerId, basket, address)
  ↓
  1. BasketService.GetBasketAsync(basketId)
  2. Validate items exist (CatalogService)
  3. Create Order entity
  4. PaymentService.ProcessPayment(order)
     ↓ [External call - potential timeout]
  5. CatalogContext.Orders.Add(order)
  6. SaveChangesAsync()
  7. BasketService.DeleteBasketAsync(basketId)
  ↓
Return Order (redirect to success page)
```

---

## Normal Behavior Patterns

### Successful Order
```
[INFO] OrderService: Creating order for buyer: user@example.com
[INFO] OrderService: Retrieved basket with 3 items
[INFO] OrderService: Validated all catalog items exist
[INFO] PaymentService: Processing payment for $45.99
[INFO] PaymentService: Payment authorized in 150ms
[INFO] OrderService: Order #123 created successfully
[INFO] BasketService: Basket cleared for user
```

### Expected Performance
- Simple order (3 items): <500ms
- With payment: <1000ms
- Large order (10+ items): <1500ms

---

## Known Failure Modes

### 1. Payment Timeout

**Symptom:**
```
[ERROR] PaymentService: Payment request timed out after 30000ms
[ERROR] OrderService: Order creation failed - payment timeout
[WARN] Order stuck in 'Processing' state
```

**Root Cause:**
- External payment gateway slow/unavailable
- Network issues
- Payment service not responsive

**Impact:**
- Order not completed
- User sees timeout error
- Basket not cleared
- Payment may or may not have processed (reconciliation needed)

**Diagnosis:**
- Check for "Payment.*timeout" in logs
- Look for PaymentService errors
- Check order status (stuck in Processing?)
- Verify payment gateway availability

**Solution:**
- Implement retry logic
- Increase timeout threshold
- Add async payment processing
- Implement payment status polling

**Business Impact:** **HIGH** - Orders lost, revenue impact

---

### 2. Inventory Conflict

**Symptom:**
```
[ERROR] OrderService: CatalogItem #45 out of stock
[ERROR] OrderService: Order creation failed - inventory unavailable
```

**Root Cause:**
- Item sold out between basket add and checkout
- No inventory tracking in current version
- Concurrent purchases of last item

**Impact:**
- Order creation fails
- User frustrated (had item in basket)

**Diagnosis:**
- Check for "out of stock" or "inventory" errors
- Look at item IDs mentioned
- Check catalog for item availability

**Solution:**
- Implement inventory tracking
- Reserve items when added to basket
- Show real-time availability

**Business Impact:** **MEDIUM** - Lost sales

---

### 3. Basket Not Found

**Symptom:**
```
[ERROR] BasketService: Basket not found for user: user@example.com
[ERROR] OrderService: Cannot create order - basket is empty or missing
```

**Root Cause:**
- Basket expired or deleted
- Session lost
- Basket ID mismatch

**Impact:**
- Checkout fails
- User must recreate basket

**Diagnosis:**
- Check for "Basket not found" errors
- Verify basket ID in request
- Check basket expiration settings

**Solution:**
- Extend basket lifetime
- Implement basket persistence
- Add user session management

**Business Impact:** **MEDIUM** - Abandoned carts

---

### 4. Database Save Failure

**Symptom:**
```
[ERROR] OrderService: Failed to save order to database
[ERROR] DbUpdateException: An error occurred while updating the entries
[ERROR] SQLite Error: database is locked
```

**Root Cause:**
- Database write conflict
- Transaction deadlock
- Constraint violation

**Impact:**
- Order not persisted
- Payment may have succeeded but no order record
- Data inconsistency

**Diagnosis:**
- Check for SaveChangesAsync errors
- Look for database locking
- Verify transaction handling

**Solution:**
- Implement retry logic for locks
- Use idempotent operations
- Add transaction rollback handling

**Business Impact:** **CRITICAL** - Payment without order record

---

## Command/Query Handlers (MediatR)

### CreateOrderCommand
**Handler:** `CreateOrderCommandHandler`
**Validates:**
- User authenticated
- Basket exists and not empty
- Shipping address valid

**Returns:** Order ID or error

### GetOrderQuery
**Handler:** `GetOrderQueryHandler`
**Returns:** Order details for user's orders

---

## Dependencies

### Requires
- **BasketService** (load basket items)
- **CatalogService** (validate items exist)
- **IPaymentService** (process payment)
- **CatalogContext** (save order)

### Used By
- **Web UI** (checkout process)
- **Public API** (programmatic orders)
- **Admin Panel** (order management)

---

## Typical Error Patterns in Logs

### Pattern: Payment Gateway Issues
```
[INFO] PaymentService: Initiating payment for $45.99
[WARN] PaymentService: Payment gateway slow to respond
[ERROR] PaymentService: Payment request timed out after 30000ms
[ERROR] OrderService: Order creation failed
```
→ **Diagnosis:** External service timeout

### Pattern: Empty Basket at Checkout
```
[WARN] BasketService: Basket is empty for user
[ERROR] OrderService: Cannot create order - no items in basket
```
→ **Diagnosis:** Basket cleared or expired

### Pattern: Database Conflicts
```
[ERROR] OrderService: Failed to save order
[ERROR] DbUpdateException: database is locked
[ERROR] Retry attempt 1 of 3
```
→ **Diagnosis:** Write contention

---

## Investigation Checklist

When order errors occur:

1. **Check basket status:**
   ```sql
   SELECT * FROM Baskets WHERE BuyerId = 'user@example.com';
   SELECT * FROM BasketItems WHERE BasketId = 123;
   ```

2. **Check payment logs:**
   - Look for PaymentService entries
   - Check response times
   - Look for timeout patterns

3. **Verify order state:**
   ```sql
   SELECT Id, BuyerId, OrderDate, Status FROM Orders 
   WHERE BuyerId = 'user@example.com' 
   ORDER BY OrderDate DESC;
   ```

4. **Check for concurrent operations:**
   - Multiple checkout attempts?
   - Basket modifications during checkout?

5. **Test payment service:**
   - Is gateway reachable?
   - Are credentials valid?
   - Test transaction manually

---

## Related Components
- **BasketAgent** - Investigates basket issues affecting orders
- **DatabaseAgent** - Investigates order persistence failures
- **CatalogAgent** - Investigates item validation failures

---

**Last Updated:** 2026-05-26  
**Domain:** Order Processing / Checkout
