# Basket Service - eShopOnWeb

## Overview
The Basket Service manages user shopping carts (baskets) including adding/removing items and basket persistence.

---

## Entities

### Basket
**Location:** `ApplicationCore/Entities/BasketAggregate/Basket.cs`

**Properties:**
- `Id` (int) - Primary key
- `BuyerId` (string) - User identifier (email or anonymous ID)
- `Items` (List<BasketItem>) - Items in cart

### BasketItem
**Properties:**
- `Id` (int)
- `UnitPrice` (decimal)
- `Quantity` (int)
- `CatalogItemId` (int) - Reference to catalog product

---

## BasketService

**Location:** `ApplicationCore/Services/BasketService.cs`

### Key Methods

#### AddItemToBasket
```csharp
Task AddItemToBasketAsync(int basketId, int catalogItemId, decimal price, int quantity);
```
**Process:**
1. Get basket
2. Check if item already exists
3. If exists: increment quantity
4. If new: add new BasketItem
5. Save to database

#### SetQuantities
```csharp
Task SetQuantitiesAsync(int basketId, Dictionary<int, int> quantities);
```
**Process:**
1. Get basket
2. Update quantities for multiple items
3. Save to database

**Concurrency Risk:** High - multiple users/tabs can modify same basket

---

## Request Flow

### Add Item to Basket
```
User → POST /Basket/Index (Add to Cart)
  ↓
BasketController.Index(catalogItemId, quantity)
  ↓
BasketService.AddItemToBasketAsync(basketId, itemId, price, qty)
  ↓
  1. GetBasketAsync(basketId)
  2. basket.Items.Find(item => item.CatalogItemId == itemId)
  3. If found: item.Quantity += quantity
     If not: basket.Items.Add(new BasketItem(...))
  4. CatalogContext.Baskets.Update(basket)
  5. SaveChangesAsync()
  ↓
Return updated basket
```

---

## Normal Behavior Patterns

### Successful Add to Basket
```
[INFO] BasketService: Adding item #5 to basket for user@example.com
[INFO] BasketService: Item already in basket, incrementing quantity
[INFO] BasketService: Basket updated - now has 3 items, total: $45.99
```

### Expected Performance
- Add item: <100ms
- Update quantity: <50ms
- Load basket: <50ms

---

## Known Failure Modes

### 1. Race Condition / Concurrent Modification

**Symptom:**
```
[WARN] BasketService: Concurrent modification detected
[ERROR] DbUpdateConcurrencyException: The database operation expected to affect 1 row(s) but actually affected 0 row(s)
[ERROR] BasketService: Failed to update basket - concurrent modification
```

**Root Cause:**
- User opens multiple tabs
- Updates basket in both tabs simultaneously
- Second update overwrites first
- Or: DbConcurrency exception

**Impact:**
- Lost basket items
- Wrong quantities
- User frustration

**Diagnosis:**
- Check for DbUpdateConcurrencyException
- Look for multiple requests with same timestamp
- Check for "concurrent modification" warnings

**Solution:**
- Implement optimistic concurrency (RowVersion)
- Add retry logic
- Reload basket before each update
- Use last-write-wins or merge strategies

**Business Impact:** **MEDIUM** - Items lost from cart

---

### 2. Basket Not Found

**Symptom:**
```
[WARN] BasketService: Basket not found for buyerId: user@example.com
[INFO] BasketService: Creating new basket for user
```

**Root Cause:**
- First-time user
- Session expired
- Basket deleted

**Impact:**
- Empty cart shown (expected for new users)
- Previous items lost (if session expired)

**Diagnosis:**
- Check if "Basket not found" followed by "Creating new"
- Verify buyer ID consistency
- Check basket expiration settings

**Solution:**
- Automatic basket creation (current behavior)
- Persist baskets longer
- Link baskets to authenticated users

**Business Impact:** **LOW** (if new user), **HIGH** (if session lost with items)

---

### 3. Invalid Catalog Item

**Symptom:**
```
[ERROR] BasketService: CatalogItem #999 does not exist
[ERROR] BasketService: Cannot add non-existent item to basket
```

**Root Cause:**
- Item deleted from catalog
- Invalid item ID in request
- Cache stale

**Impact:**
- Add to cart fails
- User confused

**Diagnosis:**
- Check for "does not exist" errors
- Verify item ID against catalog
- Check if item was recently deleted

**Solution:**
- Validate item exists before adding
- Return friendly error message
- Redirect to catalog

**Business Impact:** **LOW** - Single operation fails

---

### 4. Database Save Failure

**Symptom:**
```
[ERROR] BasketService: Failed to save basket changes
[ERROR] SQLite Error: database is locked
```

**Root Cause:**
- Database write conflict
- Transaction not completed
- Connection issue

**Impact:**
- Basket changes lost
- User must retry

**Diagnosis:**
- Check for SaveChangesAsync failures
- Look for database locking
- Verify database connectivity

**Solution:**
- Implement retry logic
- Reduce transaction scope
- Handle transient failures gracefully

**Business Impact:** **MEDIUM** - Degraded UX

---

## Concurrency Considerations

### High Concurrency Scenarios
1. **Multiple Tabs:** User opens catalog in 2+ tabs, adds items from both
2. **Quick Clicks:** User rapidly clicks "Add to Cart"
3. **Checkout + Edit:** User updates basket while checkout is processing

### Mitigation Strategies
- Optimistic concurrency (RowVersion field)
- Reload basket before each update
- Client-side debouncing
- Transaction isolation levels

---

## Dependencies

### Requires
- **CatalogContext** (basket persistence)
- **CatalogService** (validate items exist)

### Used By
- **OrderService** (load basket for checkout)
- **Web UI** (display cart, update quantities)
- **Public API** (programmatic cart management)

---

## Typical Error Patterns in Logs

### Pattern: Concurrent Updates
```
[INFO] BasketService: User updating basket
[INFO] BasketService: User updating basket  (same timestamp)
[WARN] BasketService: Concurrent modification detected
[ERROR] DbUpdateConcurrencyException
```
→ **Diagnosis:** Multiple simultaneous updates

### Pattern: Session Loss
```
[WARN] BasketService: Basket not found for buyerId: anon-abc123
[INFO] BasketService: Creating new basket
[WARN] Previous basket with 5 items lost
```
→ **Diagnosis:** Session expired, items lost

### Pattern: Invalid Items
```
[ERROR] BasketService: CatalogItem #45 does not exist
[ERROR] Cannot add item to basket
```
→ **Diagnosis:** Stale product reference

---

## Investigation Checklist

When basket errors occur:

1. **Check basket state:**
   ```sql
   SELECT * FROM Baskets WHERE BuyerId = 'user@example.com';
   SELECT * FROM BasketItems WHERE BasketId = 123;
   ```

2. **Check for concurrent modifications:**
   - Look for multiple requests at same timestamp
   - Check for DbUpdateConcurrencyException
   - Verify request patterns

3. **Verify item validity:**
   ```sql
   SELECT Id, Name FROM CatalogItems WHERE Id IN (1, 5, 10);
   ```

4. **Check session persistence:**
   - Is buyerId consistent across requests?
   - Are anonymous IDs being regenerated?

5. **Test manually:**
   ```bash
   # Add item to basket
   curl -X POST http://localhost:5001/Basket/Index?catalogItemId=1&quantity=2
   ```

---

## Related Components
- **CatalogAgent** - Investigates item availability issues
- **DatabaseAgent** - Investigates basket persistence failures
- **OrderAgent** - Uses basket data for checkout

---

**Last Updated:** 2026-05-26  
**Domain:** Basket / Shopping Cart
