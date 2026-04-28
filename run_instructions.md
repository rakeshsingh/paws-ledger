# PawsLedger - Local Deployment Instructions

Follow these steps to set up and run PawsLedger locally on your machine.

## Prerequisites

- Python 3.9 or higher
- `pip` (Python package installer)

## Setup

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd paws-ledger
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - **Linux/macOS**:
     ```bash
     source venv/bin/activate
     ```
   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Seed the database** (Optional):
   This will populate the database with initial sample data.
   ```bash
   python seed_db.py
   ```

## Running the Application

To run the application on `0.0.0.0` (accessible from other devices on your network) at port `8080`:

### Option 1: Using the main entry point
The application is pre-configured to run on `0.0.0.0:8080` when executed directly.
```bash
python -m app.main
```

### Option 2: Using Uvicorn directly
```bash
uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8080 --reload
```

The UI will be available at `http://localhost:8080` (or the IP address of the machine).
The API documentation (Swagger UI) will be available at `http://localhost:8080/docs`.
