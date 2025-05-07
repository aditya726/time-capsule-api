Time-Capsule

A FastAPI-based web application where users can create time-locked digital capsules. Each capsule contains a message that can only be unlocked after a specified future date. Capsules automatically expire 30 days after the unlock date.
🚀 Project Overview

    Tech stack: FastAPI, SQLAlchemy, PostgreSQL, JWT authentication, Pydantic.

    Core features:

        User authentication system.

        Create, view, update, and delete time capsules.

        Capsules unlockable only after their scheduled time.

        Automatic expiration check running hourly.

This project allows users to leave time-delayed messages — like a digital time capsule — that become available after a set unlock date.
🛠 How to Run the App
1️⃣ Clone the repository

git clone <your-repo-url>
cd <your-repo-directory>

2️⃣ Create and activate a virtual environment

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3️⃣ Install dependencies

pip install -r requirements.txt

4️⃣ Set up environment variables

Create a .env file in the project root with:

DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>
SECRET_KEY=<your-secret-key>
ALGORITHM=HS256

5️⃣ Run the FastAPI server

uvicorn main:app --reload

By default, the app runs at http://127.0.0.1:8000.

You can explore the API docs at:

    Swagger UI: http://127.0.0.1:8000/docs
