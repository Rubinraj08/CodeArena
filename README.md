# CodeArena 🚀

CodeArena is a gamified coding platform built using Flask where users can solve coding challenges, earn badges, and compete with others in an interactive environment.

---

## ✨ Features

- 🔐 User Authentication & Profiles
- 💻 Coding Challenges with Test Cases
- ⚡ Real-Time Code Execution & Validation
- 🏆 Badge & Achievement System
- 📊 Leaderboards and Competition
- 🤖 AI-Powered Code Assistance using Groq API
- 🛠️ Admin Panel for Challenge Management

---

## 🛠️ Tech Stack

- Python
- Flask
- SQLite
- HTML/CSS/JavaScript
- Groq API

---

## 📂 Project Structure

```bash
CodeArena/
│
├── app.py               # Main Flask application
├── models.py            # Database models
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
├── static/              # CSS, JS, Images
├── instance/            # Database files
├── .env                 # Environment variables
└── README.md
```

---

## ⚙️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Rubinraj08/CodeArena.git
cd CodeArena
```

### 2️⃣ Create a Virtual Environment

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux / Mac
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Configure Environment Variables

Create a `.env` file in the project root directory and add:

```env
GROQ_API_KEY=your_groq_api_key_here
```

---

### 5️⃣ Set Up Database

```bash
python models.py
```

---

## ▶️ Run the Application

```bash
python app.py
```

Open your browser and visit:

```bash
http://localhost:5000
```

---

## 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API Key for AI code assistance |

---

---

## 📜 License

This project is licensed under the MIT License.

---
