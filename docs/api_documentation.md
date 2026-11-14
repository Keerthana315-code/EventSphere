# EventSphere API Documentation

## 1. Introduction

EventSphere provides REST APIs for authentication, venues, events,
ticket types, bookings, digital tickets, private hire, and administration.

Base URL (local development):

http://127.0.0.1:8000

Interactive API documentation:

http://127.0.0.1:8000/docs

## 2. Authentication

### Register

POST /auth/register

Creates a new user account.

### Login

POST /auth/login

Authenticates a user and returns an access token.

### Current User

GET /auth/me

Returns the authenticated user's details.

Protected endpoints require:

Authorization: Bearer ACCESS_TOKEN

## 3. Venues

| Method | Endpoint | Description |
|---|---|---|
| POST | /venues/ | Create venue (admin) |
| GET | /venues/ | List venues |
| GET | /venues/{venue_id} | Get venue |
| PUT | /venues/{venue_id} | Update venue (admin) |
| DELETE | /venues/{venue_id} | Deactivate venue (admin) |

## 4. Events

| Method | Endpoint | Description |
|---|---|---|
| POST | /events/ | Create event (admin) |
| GET | /events/ | List published events |
| GET | /events/{event_id} | Get event details |
| PUT | /events/{event_id} | Update event |
| POST | /events/{event_id}/publish | Publish event |
| POST | /events/{event_id}/cancel | Cancel event |

## 5. Ticket Types

| Method | Endpoint | Description |
|---|---|---|
| POST | /ticket-types/ | Create ticket type |
| GET | /ticket-types/{event_id} | List event ticket types |
| PUT | /ticket-types/{ticket_type_id} | Update ticket type |

## 6. Bookings

| Method | Endpoint | Description |
|---|---|---|
| POST | /bookings/ | Create booking |
| GET | /bookings/my | List my bookings |
| GET | /bookings/{booking_id} | Get booking details |
| POST | /bookings/{booking_id}/cancel | Cancel booking |

## 7. Digital Tickets

| Method | Endpoint | Description |
|---|---|---|
| GET | /tickets/my | List my tickets |
| GET | /tickets/{ticket_id}/qr | Get ticket QR code |
| POST | /tickets/scan | Scan and validate ticket |

## 8. Private Hire

| Method | Endpoint | Description |
|---|---|---|
| POST | /private-hire/ | Submit private hire request |
| GET | /private-hire/my | List my requests |
| GET | /private-hire/ | List requests (admin) |
| PATCH | /private-hire/{request_id}/cancel | Cancel request |

## 9. Admin Dashboard

| Method | Endpoint | Description |
|---|---|---|
| GET | /admin-api/stats | Dashboard statistics |
| GET | /admin-api/bookings | List all bookings |
| GET | /admin-api/users | List all users |
| GET | /agent-logs/ | View agent message logs |

All admin endpoints require an authenticated administrator.

## 10. Health Check

GET /health

Checks whether the application is running.

## 11. API Responses

Successful requests return JSON data.

Common HTTP status codes:

| Code | Meaning |
|---|---|
| 200 | Request successful |
| 201 | Resource created |
| 400 | Invalid request |
| 401 | Authentication required |
| 403 | Permission denied |
| 404 | Resource not found |
| 409 | Conflict |
| 422 | Validation error |
| 500 | Internal server error |

## 12. Payment Simulation

EventSphere uses simulated payments for demonstration.
No real payment information is collected or processed.

## 13. Security

- Passwords are hashed.
- Protected endpoints use bearer-token authentication.
- Admin operations require administrator privileges.
- Ticket codes are unique.
- Duplicate ticket check-ins are rejected.