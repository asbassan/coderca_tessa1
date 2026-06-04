# Catalog Service - eShopOnWeb

## Overview
The Catalog Service manages the product catalog including items, brands, and types. It is the core of the e-commerce functionality.

---

## Entities

### CatalogItem
**Location:** `ApplicationCore/Entities/CatalogAggregate/CatalogItem.cs`

**Properties:**
- `Id` (int) - Primary key
- `Name` (string) - Product name
- `Description` (string) - Product description
- `Price` (decimal) - Unit price
- `PictureUri` (string) - Image path
- `CatalogTypeId` (int) - Foreign key to CatalogType
- `CatalogBrandId` (int) - Foreign key to CatalogBrand

**Example:**
```json
{
  "Id": 1,
  "Name": ".NET Bot Black Hoodie",
  "Description": "Relaxed fit hoodie with .NET Bot logo",
  "Price": 19.50,
  "CatalogTypeId": 2,
  "CatalogBrandId": 1
}
```

### CatalogBrand
**Properties:**
- `Id` (int) - Primary key
- `Brand` (string) - Brand name (e.g., ".NET", "Other")

### CatalogType
**Properties:**
- `Id` (int) - Primary key
- `Type` (string) - Category name (e.g., "Mug", "T-Shirt", "Sheet")

---

## CatalogService

**Location:** `ApplicationCore/Services/CatalogService.cs`

### Key Methods

#### GetCatalogItems
```csharp
Task<PaginatedList<CatalogItem>> GetCatalogItemsAsync(
    int pageIndex, 
    int itemsPage, 
    int? brandId, 
    int? typeId
);
```
**Purpose:** Retrieve paginated product list with optional filters

**Dependencies:** CatalogContext (database)

**Returns:** List of CatalogItems with navigation properties loaded

#### GetCatalogItemById
```csharp
Task<CatalogItem> GetCatalogItemByIdAsync(int catalogItemId);
```
**Purpose:** Get single product by ID

---

## Request Flow

### Browse Catalog
```
User → GET /Catalog?page=1
  ↓
CatalogController.Index(page, brandId, typeId)
  ↓
CatalogService.GetCatalogItemsAsync(page, pageSize, brandId, typeId)
  ↓
CatalogContext.CatalogItems
    .Include(CatalogBrand)
    .Include(CatalogType)
    .Where(filters)
    .Skip(skip)
    .Take(pageSize)
  ↓
SQLite Query
  ↓
Return PaginatedList<CatalogItem>
```

---

## Normal Behavior Patterns

### Successful Catalog Load
```
[INFO] CatalogController: Loading catalog page 1
[INFO] CatalogService: Retrieved 10 items, filtered by brand: 1
[INFO] Query took 15ms
```

### Typical Queries
- List all products (no filters)
- Filter by brand
- Filter by type
- Filter by both brand and type
- Paginate through results (10 items per page)

### Expected Performance
- Simple listing: <50ms
- Filtered query: <100ms
- With images: <200ms

---

## Known Failure Modes

### 1. Database Not Available

**Symptom:**
```
[ERROR] An exception occurred while iterating over the results of a query for context type 'CatalogContext'
[ERROR] SQLite Error 1: 'no such table: CatalogBrands'
```

**Root Cause:**
- Database tables not created (migrations not run)
- Database file missing or empty
- Connection string incorrect

**Impact:**
- ALL catalog operations fail
- Users see error page or empty catalog
- No products visible

**Diagnosis:**
- Check for "no such table: CatalogBrands" or "CatalogItems" or "CatalogTypes"
- Verify database file exists and size > 0
- Check startup logs for seeding errors

**Solution:**
```bash
dotnet ef database update --context CatalogContext
```

**Business Impact:** **CRITICAL** - Entire catalog unavailable

---

### 2. Catalog Data Missing

**Symptom:**
```
[WARN] CatalogService: No catalog items found
[INFO] Returned empty product list
```

**Root Cause:**
- Database exists but not seeded
- Seed data failed to insert
- Manual data deletion

**Impact:**
- Catalog loads but shows "No products available"
- Users can't browse or purchase

**Diagnosis:**
- Query: `SELECT COUNT(*) FROM CatalogItems` returns 0
- Check seeding logs for errors
- Verify CatalogContextSeed ran successfully

**Solution:**
- Delete database and restart app (triggers reseed)
- Or manually run seeding code

**Business Impact:** **HIGH** - Users see empty store

---

### 3. Slow Query Performance

**Symptom:**
```
[WARN] CatalogService: Query took 2500ms
[WARN] Possible N+1 query detected
```

**Root Cause:**
- Missing `.Include()` for navigation properties
- Large result sets without pagination
- Complex filters without indexes

**Impact:**
- Slow page loads
- Poor user experience
- Potential timeouts

**Diagnosis:**
- Check query duration in logs
- Look for multiple DB round-trips
- Profile EF Core queries

**Solution:**
- Add `.Include(i => i.CatalogBrand).Include(i => i.CatalogType)`
- Ensure pagination is working
- Add database indexes if needed

**Business Impact:** **MEDIUM** - Degraded performance

---

### 4. Null Reference Errors

**Symptom:**
```
[ERROR] NullReferenceException in CatalogController
[ERROR] Object reference not set to an instance of an object
[ERROR] at CatalogController.Index() line 45
```

**Root Cause:**
- CatalogService returns null unexpectedly
- Missing null checks
- Database returns incomplete data

**Impact:**
- Specific catalog operations crash
- Error page shown to user

**Diagnosis:**
- Check stack trace for null access point
- Verify service method return types
- Check for missing navigation property loading

**Solution:**
- Add null checks in controllers
- Ensure service methods never return null (use empty lists)
- Load all required navigation properties

**Business Impact:** **MEDIUM** - Some operations fail

---

## Dependencies

### Requires
- **CatalogContext** (database access)
  - If database unavailable → All operations fail
- **Seeded Data** (CatalogBrands, CatalogTypes, CatalogItems)
  - If data missing → Empty catalog

### Used By
- **Web UI** (main catalog browsing)
- **Public API** (external integrations)
- **BasketService** (validate items exist)
- **OrderService** (load item details for orders)

---

## Typical Error Patterns in Logs

### Pattern: Infrastructure Failure
```
[ERROR] no such table: CatalogBrands
[ERROR] An exception occurred while iterating over the results
[ERROR] CatalogService.GetCatalogItemsAsync failed
```
→ **Diagnosis:** Database not initialized

### Pattern: Data Missing
```
[WARN] No CatalogItems found matching criteria
[WARN] Returned empty list
[INFO] User saw "No products available" message
```
→ **Diagnosis:** Database not seeded or data deleted

### Pattern: Performance Degradation
```
[WARN] CatalogService: Query took 1500ms
[WARN] CatalogService: Query took 2200ms
[WARN] CatalogService: Query took 3000ms
```
→ **Diagnosis:** N+1 problem or missing indexes

---

## Investigation Checklist

When catalog errors occur:

1. **Check database availability:**
   - Do catalog.db file exist?
   - Are tables created? (`SELECT name FROM sqlite_master`)

2. **Check data seeded:**
   ```sql
   SELECT COUNT(*) FROM CatalogBrands;  -- Should return 10
   SELECT COUNT(*) FROM CatalogTypes;   -- Should return 2
   SELECT COUNT(*) FROM CatalogItems;   -- Should return 12
   ```

3. **Check service logs:**
   - Look for CatalogService method calls
   - Check query durations
   - Look for exception patterns

4. **Verify request flow:**
   - CatalogController called?
   - CatalogService called?
   - Database queries executed?

5. **Test manually:**
   ```bash
   curl http://localhost:5001/Catalog
   # Should return HTML with products
   ```

---

## Related Components
- **DatabaseAgent** - Investigates underlying DB issues
- **BasketAgent** - Depends on catalog to validate items
- **OrderAgent** - Depends on catalog for product details

---

**Last Updated:** 2026-05-26  
**Domain:** Catalog / Product Management
