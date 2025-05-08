Deployed Link : https://time-capsule-api-4rob.onrender.com
---
-to test all the api endpoints go to https://time-capsule-api-4rob.onrender.com/docs
-After registering on auth/register you can get your access token fron auth/login.
-To test all protected endpoints please click the Authorize button on top right corner and enter your username and password


# Time-Capsule

A FastAPI-based web application where users can create time-locked digital capsules. Each capsule contains a message that can only be unlocked after a specified future date. Capsules automatically expire 30 days after the unlock date.

---

## 🚀 Project Overview

- **Tech stack**: FastAPI, SQLAlchemy, PostgreSQL, JWT authentication, Pydantic.
- **Core features**:
  - User authentication system.
  - Create, view, update, and delete time capsules.
  - Capsules unlockable only after their scheduled time.
  - Automatic expiration check running hourly.
  
This project allows users to leave time-delayed messages — like a digital time capsule — that become available after a set unlock date.

---

## 🛠 How to Run the App

### 1️⃣ Clone the repository
```bash
git clone https://github.com/aditya726/time-capsule-api.git
cd <your-repo-directory>
```

### 2️⃣ Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Set up environment variables
Create a `.env` file in the project root with:
```
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>
SECRET_KEY=<your-secret-key>
ALGORITHM=HS256
```

### 5️⃣ Run the FastAPI server
```bash
uvicorn main:app --reload
```

By default, the app runs at [http://127.0.0.1:8000](http://127.0.0.1:8000).

You can explore the API docs and test all API endpoints at:
- Swagger UI: `http://127.0.0.1:8000/docs`
---


### 📌 Notes

- The app uses an hourly background task to mark capsules as expired.
- Unlock codes are **12-character random strings**.
- Capsules can be deleted or updated **only before** their unlock time.
- After the unlock date, capsules are accessible for 30 days, after which they are marked as **expired**.

---

