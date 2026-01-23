# PRD: Manager Flight Creation - Staff Availability Blocking

## Product Overview
When a manager attempts to create a new flight, the system must ensure that both aircraft and staff are available at the selected departure time. If either is unavailable, the system should block progression to step 2 (staff selection) and suggest the earliest timestamp when both resources become available.

## Problem Statement
Currently, managers can proceed to step 2 even when no staff or aircraft are available, leading to confusion and inability to complete flight creation. The system should proactively prevent this by validating availability in step 1 and providing actionable suggestions.

## User Story
**As a** manager  
**I want** the system to block flight creation when staff/aircraft are unavailable and suggest the earliest available time  
**So that** I can efficiently schedule flights without wasting time on impossible configurations

## Requirements

### Functional Requirements

#### FR1: Availability Validation in Step 1
- **When:** Manager submits flight details in step 1 (date, time, origin, destination)
- **System must:**
  1. Check if aircraft are available at the selected departure date/time
  2. Check if staff members are available at the origin airport at the selected departure time
  3. If both available → proceed to step 2 (staff selection)
  4. If either unavailable → block progression and show suggestion

#### FR2: Staff Availability Check
- Staff member is available at origin airport if:
  - Their last completed flight landed at the origin airport AND arrival time ≤ requested departure time
  - OR they are on a future flight (Active/Full) that will arrive at origin airport before/at requested departure time
  - AND either:
    - They have no next flight scheduled, OR
    - Their next flight departs after the requested departure time
  - OR they are new staff (never been on any flight)

#### FR3: Aircraft Availability Check
- Aircraft is available if:
  - Not assigned to another flight at the same departure date/time
  - Meets size requirements (Big for Long flights)

#### FR4: Blocking and Suggestion
- **When:** Staff or aircraft unavailable
- **System must:**
  1. Block progression to step 2
  2. Find earliest timestamp when both staff AND aircraft become available
  3. Display alert message with:
     - Clear explanation of unavailability
     - Suggested timestamp (date and time)
     - Instruction to update departure time to after suggested time
  4. Keep manager on step 1 form with pre-filled values
  5. Allow manager to update departure date/time and resubmit

#### FR5: Suggestion Algorithm
- Query all future flights arriving at origin airport
- For each arrival time, check:
  - How many staff members will be available
  - If aircraft are available at that time
- Select earliest timestamp where:
  - At least required number of staff available (based on aircraft size)
  - At least one suitable aircraft available
- If no future availability found → show appropriate message

#### FR6: Success Flow
- **When:** Manager updates to timestamp after suggested time and resubmits
- **System must:**
  1. Re-validate availability
  2. If available → proceed to step 2
  3. If still unavailable → show new suggestion (recursive)

### Non-Functional Requirements

#### NFR1: Performance
- Availability checks must complete within 2 seconds
- Database queries should be optimized with proper indexes

#### NFR2: User Experience
- Error messages must be clear and actionable
- Suggested timestamps must be precise (date + time)
- Form should retain user input when showing suggestions

#### NFR3: Data Integrity
- All availability checks must be atomic
- No race conditions between availability check and flight creation

## Acceptance Criteria

### AC1: Block When No Staff Available
- **Given:** Manager selects departure time Y, no staff available at origin airport
- **When:** Manager submits step 1 form
- **Then:**
  - System blocks progression
  - Shows alert: "No available staff at [airport] for [timestamp Y]. Earliest available time: [timestamp T]. Please update departure time to after [timestamp T]."
  - Manager remains on step 1
  - Form retains all input values

### AC2: Block When No Aircraft Available
- **Given:** Manager selects departure time Y, no aircraft available
- **When:** Manager submits step 1 form
- **Then:**
  - System blocks progression
  - Shows alert: "No suitable aircraft available at [timestamp Y]. Earliest available time: [timestamp T]. Please update departure time to after [timestamp T]."
  - Manager remains on step 1

### AC3: Block When Both Unavailable
- **Given:** Manager selects departure time Y, neither staff nor aircraft available
- **When:** Manager submits step 1 form
- **Then:**
  - System blocks progression
  - Shows alert with earliest timestamp when BOTH become available
  - Manager remains on step 1

### AC4: Success After Update
- **Given:** Manager receives suggestion for timestamp T
- **When:** Manager updates departure time to after T and resubmits
- **Then:**
  - System validates availability
  - If available → proceeds to step 2
  - If still unavailable → shows new suggestion

### AC5: Immediate Success
- **Given:** Manager selects departure time Y, both staff and aircraft available
- **When:** Manager submits step 1 form
- **Then:**
  - System proceeds directly to step 2
  - No blocking or suggestions shown

## Technical Implementation

### Database Queries Required
1. Staff availability query (already implemented, needs refinement)
2. Aircraft availability query (already implemented)
3. Future availability suggestion query (needs implementation)

### Code Changes
- Modify `manager_add_flight_step1` POST handler
- Add availability validation before redirect to step 2
- Add suggestion algorithm
- Update flash messages

### Edge Cases
- No future flights scheduled → show "No availability in foreseeable future"
- Staff available but wrong type (e.g., need long-haul certified) → include in suggestion
- Multiple aircraft sizes → check availability for each size

## Success Metrics
- Reduction in failed flight creation attempts
- Reduction in time spent on step 2 with no available staff
- Increase in successful flight creation on first attempt

## Out of Scope
- Automatic rescheduling of existing flights to free up resources
- Notifications when resources become available
- Batch flight creation
