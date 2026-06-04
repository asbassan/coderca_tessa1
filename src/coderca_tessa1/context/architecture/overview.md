# eShopOnWeb Architecture Overview

## Application Structure

eShopOnWeb is a .NET 8 monolithic web application demonstrating Clean Architecture patterns.

### Projects

| Project | Purpose | Technologies |
|---------|---------|--------------|
| **Web** | ASP.NET Core MVC + Razor Pages | Main user interface |
| **ApplicationCore** | Business logic, entities, services | Domain-driven design |
| **Infrastructure** | Data access, external services | EF Core, Identity |
| **BlazorAdmin** | Admin panel | Blazor WebAssembly |
| **PublicApi** | REST API | ASP.NET Core Web API |

---

## Key Components

### 1. **Catalog System**
- **Entities:** CatalogItem, CatalogBrand, CatalogType
- **Services:** CatalogService
- **Context:** CatalogContext (EF Core DbContext)
- **Purpose:** Product catalog management

### 2. **Basket (Shopping Cart)**
- **Entities:** Basket, BasketItem
- **Services:** BasketService
- **Purpose:** User shopping cart management

### 3. **Order Processing**
- **Entities:** Order, OrderItem
- **Services:** OrderService
- **Handlers:** CreateOrderCommandHandler (MediatR)
- **Purpose:** Order creation, payment integration

### 4. **Identity & Authentication**
- **Context:** AppIdentityDbContext
- **Services:** IdentityTokenClaimService
- **Purpose:** User accounts, authentication

---

## Data Layer

### Entity Framework Core 8

**DbContexts:**
```
CatalogContext
├── CatalogItems
├── CatalogBrands
├── CatalogTypes
└── Orders

AppIdentityDbContext
├── Users
├── Roles
└── UserRoles
```

**Database:** SQLite (development)
**Migrations:** Infrastructure/Data/Migrations/

---

## Request Flow

```
User Request
    ↓
Controller (Web)
    ↓
Service (ApplicationCore)
    ↓
Repository (Infrastructure)
    ↓
DbContext (Infrastructure)
    ↓
SQLite Database
```

---

## Dependencies

### Service Dependencies
- **CatalogService** → CatalogContext (database)
- **BasketService** → CatalogContext (validate items)
- **OrderService** → CatalogContext + BasketService + IPaymentService

### Infrastructure Dependencies
- All services require database connectivity
- All operations logged via Serilog
- Authentication via ASP.NET Core Identity

---

## Common Failure Modes

1. **Database Not Initialized**
   - Symptom: "no such table" errors
   - Cause: Migrations not run
   - Impact: All database operations fail

2. **Database Connection Issues**
   - Symptom: Connection timeout, locked database
   - Cause: Pool exhaustion, concurrent writes
   - Impact: Intermittent failures

3. **Catalog Data Missing**
   - Symptom: Empty product listings
   - Cause: Database not seeded
   - Impact: Users see no products

4. **Payment Gateway Timeout**
   - Symptom: Order stuck in "Processing"
   - Cause: External service delay
   - Impact: Orders not completed

---

## Startup Sequence

```
1. Program.cs initializes
2. Configure services (DI)
3. Configure database contexts
4. Configure Serilog
5. Build app
6. Seed database (if needed)
7. Start web server
```

**Critical:** Database seeding happens on first run. If migrations not applied, seeding fails.

---

## Technology Stack

- **.NET 8:** Runtime
- **ASP.NET Core:** Web framework
- **EF Core 8:** ORM
- **SQLite:** Database (dev)
- **MediatR:** Command/query handling
- **Serilog:** Structured logging
- **AutoMapper:** Object mapping

---

## Relevant Code Paths

### Catalog Operations
```
GET /Catalog
  → CatalogController.Index()
    → CatalogService.GetCatalogItems()
      → CatalogContext.CatalogItems
        → SQLite query
```

### Order Creation
```
POST /Basket/Checkout
  → BasketController.Checkout()
    → CreateOrderCommandHandler.Handle()
      → OrderService.CreateOrder()
        → PaymentService.ProcessPayment()
          → CatalogContext.Orders.Add()
            → SQLite insert
```

---

## Observability

### Structured Logging
- **Sink:** SQLite (eshop-logs.db)
- **Fields:** Timestamp, Level, Message, Exception, Properties
- **Context:** Component, User, Request ID

### Log Levels
- **Information:** Normal operations, startup
- **Warning:** Recoverable issues, deprecated usage
- **Error:** Failures, exceptions, data issues

---

## Investigation Patterns

### Check These First
1. Database connectivity (catalog.db, identity.db exist?)
2. Migrations applied (tables created?)
3. Startup logs (seeding succeeded?)
4. Error patterns (same error repeated?)

### Common Root Causes
- **Database errors** → Usually infrastructure (migrations, connections)
- **Null reference errors** → Usually missing data (not seeded)
- **Timeout errors** → Usually external services or queries
- **Concurrent modification** → Usually basket operations

---

**Last Updated:** 2026-05-26  
**Version:** eShopOnWeb .NET 8 with SQLite
