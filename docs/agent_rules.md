# EventSphere - Agent Rules and Responsibilities

## 1. Introduction

EventSphere uses five software agents to coordinate venue management,
event bookings, digital tickets, waitlists, and notifications.

Each agent has a specific responsibility and communicates through
structured messages.

## 2. Message Format

Every agent message must contain:

- sender
- receiver
- performative
- content
- conversation_id
- timestamp

Supported performatives include:

- REQUEST
- INFORM
- AGREE
- REFUSE
- CONFIRM
- CANCEL

## 3. VenueAgent

### Responsibilities

- Validate venue information.
- Check venue capacity.
- Check venue availability.
- Prevent overlapping events.
- Apply a 60-minute turnaround buffer.
- Validate private hire schedules.

### Rules

1. Venue must exist and be active.
2. Event capacity must not exceed venue capacity.
3. Event end time must be later than start time.
4. Events must not overlap.
5. A 60-minute buffer must be maintained between bookings.

## 4. BookingAgent

### Responsibilities

- Validate event booking requests.
- Check event publication status.
- Check ticket type availability.
- Prevent invalid booking quantities.
- Prevent ticket overselling.

### Rules

1. Only published events can be booked.
2. Ticket quantity must be greater than zero.
3. A user can request a maximum of 10 tickets per booking.
4. Available tickets must be checked before confirmation.
5. Booking must not exceed event capacity.
6. Payment must be processed before a booking is confirmed.

## 5. TicketAgent

### Responsibilities

- Generate unique ticket codes.
- Support QR code generation.
- Validate ticket codes.
- Process ticket check-ins.

### Rules

1. Every ticket must have a unique code.
2. Cancelled tickets must be rejected.
3. Invalid tickets must be rejected.
4. A ticket can only be admitted once.
5. Tickets must belong to the correct event.
6. Check-in must follow the event's permitted time.

## 6. WaitlistAgent

### Responsibilities

- Register users on a waitlist.
- Maintain waitlist entries.
- Offer available tickets to waiting users.
- Manage temporary ticket holds.
- Expire unconfirmed offers.

### Rules

1. Only valid event and ticket type combinations are accepted.
2. A user cannot have duplicate active waitlist entries
   for the same event and ticket type.
3. Offers must have an expiry time.
4. Expired offers must not be confirmed.
5. Available tickets should be offered in waiting order.

## 7. NotificationAgent

### Responsibilities

- Notify users about booking results.
- Notify users about payment results.
- Notify users about ticket offers.
- Notify users about event updates.
- Maintain notification records.

### Rules

1. Notifications must be associated with a valid user.
2. Notification messages must contain meaningful information.
3. Notifications should be stored persistently.
4. Users should only access their own notifications.

## 8. Agent Communication

Agents communicate through structured messages.

Example:

- BookingAgent sends a REQUEST to VenueAgent.
- VenueAgent checks the venue schedule.
- VenueAgent replies with AGREE or REFUSE.
- BookingAgent processes the booking based on the response.
- NotificationAgent informs the user about the result.

## 9. Broadcast Communication

When an event is cancelled or updated, an INFORM message can be
broadcast to relevant agents.

Agents must react according to their responsibilities.

## 10. Logging

Agent messages should be recorded with:

- Sender
- Receiver
- Performative
- Content
- Conversation ID
- Timestamp

The administrator can inspect the agent message log.

## 11. Error Handling

Agents must reject invalid requests and return meaningful
error messages. Failed operations must not leave inconsistent
booking or ticket records.