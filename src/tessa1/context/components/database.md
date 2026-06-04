# Database Infrastructure - eShopOnWeb

## Overview
eShopOnWeb uses Entity Framework Core 8 with SQLite for data persistence. All data operations flow through two DbContexts.

---

## DbContexts

### CatalogContext
**Location:** `Infrastructure/Data/CatalogContext.cs`

**Entities:**
- `CatalogItem` - Products (Id, Name, Description, Price, PictureUri, CatalogTypeId, CatalogBrandId)
- `CatalogBrand` - Brands (Id, Brand)
- `CatalogType` - Categories (Id, Type)
- `Order` - Orders (Id, BuyerId, OrderDate, ShipToAddress, OrderItems)
- `OrderItem` - Line items (Id, ItemOrdered, UnitPrice, Units)
- `Basket` - Shopping carts (Id, BuyerId, Items)
- `BasketItem` - Cart items (Id, UnitPrice, Quantity, CatalogItemId)

**Connection String:** `Data Source=catalog.db`

### AppIdentityDbContext
**Location:** `Infrastructure/Identity/AppIdentityDbContext.cs`

**Entities:**
- `ApplicationUser` - User accounts
- `IdentityRole` - User roles
- Related identity tables

**Connection String:** `Data Source=identity.db`

---

## Entity Framework Configuration

### Configured in Dependencies.cs
```csharp
services.AddDbContext<CatalogContext>(c =>
    c.UseSqlite(configuration.GetConnectionString("CatalogConnection")));

services.AddDbContext<AppIdentityDbContext>(options =>
    options.UseSqlite(configuration.GetConnectionString("IdentityConnection")));
```

---

## Database Migrations

### Migration Files
**Location:** `Infrastructure/Data/Migrations/`

**Key Migrations:**
- `20201202111507_InitialModel` - Creates CatalogBrands, CatalogTypes, CatalogItems tables
- `20211026175614_FixBuyerId` - Adjusts Buyer relationship
- `20211231093753_FixShipToAddress` - Adjusts shipping address

### Applying Migrations
```bash
# Create database and tables
dotnet ef database update --context CatalogContext
dotnet ef database update --context AppIdentityDbContext
```

**CRITICAL:** Migrations MUST be run before first use. Otherwise:
- Database file exists but is empty (0 bytes or no tables)
- All queries fail with "no such table: [TableName]"
- Application cannot start properly

---

## Database Seeding

### CatalogContextSeed
**Location:** `Infrastructure/Data/CatalogContextSeed.cs`

**Seeds:**
- 10 CatalogBrands (e.g., ".NET", "Other")
- 2 CatalogTypes (e.g., "Mug", "T-Shirt")
- 12 CatalogItems (products)

**When:** On application startup, if database is empty

**Dependency:** Requires tables to exist (migrations run)

### AppIdentityDbContextSeed
**Seeds:**
- Demo user: `demouser@microsoft.com` / `Pass@word1`
- Admin user: `admin@microsoft.com` / `Pass@word1`

---

## Normal Behavior Patterns

### Successful Startup
```
[INFO] Web: App created...
[INFO] Web: Seeding Database...
[INFO] Seeded catalog with 12 items
[INFO] Created demo users
[INFO] Database seeding completed
```

### Typical Query Patterns
```csharp
// Catalog listing (common)
var items = await _context.CatalogItems
    .Include(i => i.CatalogType)
    .Include(i => i.CatalogBrand)
    .Skip(skip)
    .Take(pageSize)
    .ToListAsync();

// Order creation (less common)
_context.Orders.Add(order);
await _context.SaveChangesAsync();
```

---

## Known Failure Modes

### 1. "no such table: [TableName]"

**Error Example:**
```
SQLite Error 1: 'no such table: CatalogBrands'
at Microsoft.EntityFrameworkCore.Storage.RelationalCommand.ExecuteReaderAsync
```

**Root Cause:**
- Database migrations not applied
- Database file exists but empty (no schema)
- Wrong connection string (pointing to empty file)

**Diagnosis:**
- Check if .db file exists and size > 0
- Check if migrations ran successfully
- Query: `SELECT name FROM sqlite_master WHERE type='table'`

**Solution:**
```bash
cd src/Web
dotnet ef database update --context CatalogContext
```

**Impact:** ALL database operations fail. Application cannot function.

---

### 2. "database is locked"

**Error Example:**
```
SQLite Error 5: 'database is locked'
```

**Root Cause:**
- Concurrent write operations
- Long-running transaction
- SQLite limitation (single writer)

**Diagnosis:**
- Check for multiple simultaneous writes
- Check transaction durations
- Look for unfinished transactions

**Solution:**
- Implement retry logic
- Use Write-Ahead Logging (WAL) mode
- Reduce transaction scope

**Impact:** Intermittent write failures, especially under load

---

### 3. Connection Pool Exhaustion

**Error Example:**
```
Timeout expired. The timeout period elapsed prior to obtaining a connection from the pool.
```

**Root Cause:**
- Too many concurrent operations
- Connections not properly disposed
- Pool size too small

**Diagnosis:**
- Count active connections
- Look for leaked DbContext instances
- Check for missing `await` or `Dispose()`

**Solution:**
- Use `using` statements for DbContext
- Increase pool size (less common with SQLite)
- Fix connection leaks

**Impact:** Gradual degradation, eventual complete failure

---

### 4. Constraint Violations

**Error Example:**
```
SQLite Error 19: 'UNIQUE constraint failed: CatalogItems.Id'
```

**Root Cause:**
- Duplicate key insertion
- Manual ID assignment conflicts
- Data corruption

**Diagnosis:**
- Check entity ID generation strategy
- Look for duplicate data in seed files
- Verify auto-increment configuration

**Solution:**
- Use auto-increment IDs
- Clean and reseed database
- Fix seed data

**Impact:** Specific operations fail, data inconsistency

---

## Investigation Checklist

When database errors occur:

1. **Verify database files exist:**
   ```bash
   ls -la catalog.db identity.db
   # Should show non-zero file sizes
   ```

2. **Verify tables created:**
   ```sql
   SELECT name FROM sqlite_master WHERE type='table';
   ```

3. **Check connection strings:**
   - In appsettings.json
   - Ensure paths are correct

4. **Check migration status:**
   ```bash
   dotnet ef migrations list --context CatalogContext
   ```

5. **Review startup logs:**
   - Look for seeding success/failure
   - Check for migration warnings

6. **Test database connectivity:**
   ```bash
   sqlite3 catalog.db "SELECT COUNT(*) FROM CatalogBrands;"
   ```

---

## Typical Error Patterns in Logs

### Pattern: Infrastructure Not Ready
```
[ERROR] no such table: CatalogBrands
[ERROR] no such table: CatalogTypes  
[ERROR] no such table: CatalogItems
[ERROR] An error occurred seeding the DB
```
→ **Diagnosis:** Migrations not run

### Pattern: Concurrent Write Conflicts
```
[ERROR] database is locked
[ERROR] database is locked
[ERROR] database is locked
```
→ **Diagnosis:** Write contention, need WAL or retry logic

### Pattern: Connection Leaks
```
[WARN] Connection pool exhausted
[ERROR] Timeout obtaining connection
[ERROR] Timeout obtaining connection
```
→ **Diagnosis:** DbContext not disposed properly

---

## Dependencies

### Required For
- CatalogService (product operations)
- BasketService (cart operations)
- OrderService (order operations)
- Identity (authentication)

### Depends On
- SQLite database files (catalog.db, identity.db)
- EF Core 8
- Connection strings in configuration

---

## Related Components
- **CatalogService** - Uses CatalogContext extensively
- **OrderService** - Uses CatalogContext for order persistence
- **BasketService** - Uses CatalogContext for basket storage

---

**Last Updated:** 2026-05-26  
**Domain:** Database Infrastructure / EF Core
