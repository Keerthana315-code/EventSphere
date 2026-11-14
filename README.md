
# EventSphere

Multi-Agent Event Management and Digital Ticketing Platform.

## Project Overview

EventSphere is a web-based university event management platform.
It supports event discovery, venue management, ticket booking,
QR ticket generation and digital ticket validation.

## Technologies

- Python
- FastAPI
- SQLAlchemy
- SQLite
- PostgreSQL
- HTML
- CSS
- JavaScript
- Bootstrap
- QR Code

## Multi-Agent System

The platform includes five agents:

1. VenueAgent
2. BookingAgent
3. TicketAgent
4. WaitlistAgent
5. NotificationAgent

Agents communicate using structured messages containing
sender, receiver, performative, content and conversation ID.

## Installation

Clone the repository:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd EventSphere
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file using `.env.example`.

## Run the Application

```bash
uvicorn app.main:app --reload
```

Open:

- Website: http://127.0.0.1:8000/
- API Documentation: http://127.0.0.1:8000/docs
- Scanner: http://127.0.0.1:8000/scanner
- Admin: http://127.0.0.1:8000/admin

## Testing

Run:

```bash
pytest -v
```

## Payment

Payments are simulated for academic demonstration.
No real payment transactions are processed.

## Security

- Password hashing
- JWT authentication
- Role-based access control
- QR ticket validation
- Environment-based configuration

## Deployment

Production deployment requires PostgreSQL,
HTTPS configuration and secure environment variables.

## Author

EventSphere Project
University of Vavuniya
BSc (Hons) Information Technology
