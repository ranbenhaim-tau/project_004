# PRD: Critical Bug Fixes for FLYTAU

## Overview
Fix three critical bugs affecting ticket purchasing, order viewing, and flight cancellation functionality.

---

## Bug #1: False "Seat Already Taken" Error

### Problem
Users receive "One or more selected seats are no longer available" error when selecting available seats during ticket purchase.

### Root Cause Analysis
- Seat availability check uses `%s` placeholder instead of `?` for SQLite
- Potential type mismatch in Availability comparison (integer vs boolean)
- Query may not be finding the ticket correctly

### Acceptance Criteria
- ✅ Users can select and purchase available seats without false errors
- ✅ Only truly unavailable seats show as unavailable
- ✅ Server-side validation correctly identifies seat availability

---

## Bug #2: Internal Server Error on Order Details

### Problem
Viewing order details for orders with no customer relations (NULL MEMBER_Email and NULL GUEST_Email) causes "Internal Server Error".

### Root Cause Analysis
- Code assumes either MEMBER_Email or GUEST_Email exists
- Authorization logic may fail when both are NULL
- JOIN query might fail if no tickets exist for the order

### Acceptance Criteria
- ✅ Order details page loads for orders with NULL customer emails
- ✅ No internal server errors when viewing any order
- ✅ Proper error handling for edge cases

---

## Bug #3: Manager Cannot Cancel Flights

### Problem
Manager flight cancellation functionality does not work.

### Root Cause Analysis
- Route may not be properly configured
- Form submission may be failing
- Error handling may be swallowing exceptions

### Acceptance Criteria
- ✅ Manager can successfully cancel flights (when >=72h before departure)
- ✅ Proper error messages shown when cancellation fails
- ✅ Related orders are properly updated when flight is cancelled

---

## Implementation Plan

### Sprint 1: Bug #1 - Seat Availability
1. Fix SQL placeholder (`%s` → `?`)
2. Fix Availability type comparison
3. Add debug logging
4. QA: Test seat selection with available seats

### Sprint 2: Bug #2 - Order Details Error
1. Add NULL checks for customer emails
2. Fix authorization logic for NULL cases
3. Handle empty tickets list
4. QA: Test order details with NULL customer emails

### Sprint 3: Bug #3 - Manager Cancel Flight
1. Verify route configuration
2. Check form submission handling
3. Improve error messages
4. QA: Test manager flight cancellation

---

## Testing Strategy
- Manual testing for each bug fix
- Verify no regressions in existing functionality
- Test edge cases (NULL values, empty results, etc.)
