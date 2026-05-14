# 🔍 FindIt — Campus Lost & Found Portal

> *"It should feel as easy to use as Instagram, not as boring as a college portal."*

FindIt is a modern, Instagram-inspired lost-and-found platform designed for college campuses. Students can post lost or found items, get smart match suggestions powered by multi-signal scoring (text similarity, category, location, date proximity, and perceptual image hashing), claim items through a transparent workflow, and receive in-app + email notifications — all without needing to create an account.

---

## 🚀 Live Demo

**Deployed URL:** [https://your-app-name.streamlit.app](https://your-app-name.streamlit.app)
*(Replace with your actual Streamlit Cloud URL after deployment)*

---

## 📸 Screenshots

| Feed View | Post Item | Smart Matches | Claim Workflow |
|-----------|-----------|---------------|----------------|
| *screenshot* | *screenshot* | *screenshot* | *screenshot* |

---

## 🏗️ Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Framework** | Streamlit | Rapid prototyping, one-file deployment, built-in widgets, free hosting on Streamlit Cloud |
| **Database** | SQLite (WAL mode) | Zero-config, file-based, perfect for prototype scale; easily swappable to Postgres for production |
| **Image Matching** | `imagehash` (pHash) | Perceptual hashing detects visually similar images without a paid ML API |
| **Text Matching** | `difflib` + Jaccard | Lightweight dual-signal text similarity without external NLP dependencies |
| **Notifications** | In-app + SMTP email | In-app is zero-config; email works with any SMTP provider (Gmail, SendGrid free tier) |
| **Auth** | Email-only identity | Minimal friction — justified in DECISIONS.md |
| **Hosting** | Streamlit Community Cloud | Free, one-click deploy from GitHub |

---

## 🏃 Run Locally

### Prerequisites
- Python 3.9+
- pip

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/campus-lost-and-found.git
cd campus-lost-and-found

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py

# 4. Open http://localhost:8501 in your browser
```

### Optional: Email Notifications

Set these environment variables to enable email alerts:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASS=your-app-password
export SMTP_FROM=your-email@gmail.com
```

---

## 🌟 Key Features

### Core
- **Post lost/found items** with photo, description, category, location, and date
- **Smart matching engine** that scores items across 6 signals (category, title, description, location, date, image hash)
- **Claim workflow** with proof-of-ownership, accept/reject by poster
- **Multiple claims handling** — poster reviews all claims, accepts one, others auto-rejected
- **14 realistic seed items** so the demo is never empty

### Stretch Goals (All Implemented)
- **Email notifications** via SMTP when matches or claims occur
- **In-app notification center** with unread badges
- **Perceptual image hashing** (`imagehash` pHash) for visual similarity matching
- **Mobile-responsive design** with custom CSS, gradient nav bar, card-based layout

### UX Polish
- Instagram-style card feed with avatars, time-ago labels, type badges
- Gradient hero section and animated nav bar
- Category/location/search filters on the feed
- Match explorer for any item in the system
- One-click claim with proof-of-ownership field
- Toast notifications and balloons on successful post

---

## 📁 Project Structure

```
campus-lost-and-found/
├── app.py              # Main application (single-file Streamlit app)
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── DECISIONS.md        # Architecture & trade-off decisions log
├── exec_summary.md     # One-page executive summary for the Dean
└── findit.db           # Auto-created SQLite database (gitignored)
```

---

## 🚢 Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file path to `app.py`
5. Click **Deploy** — that's it!

---

## 👤 Author

**Ayush Sibal**
Built as part of the Data Analyst application at Infinia Technologies (FutureAI / Sirius International Holdings).

---

## 📄 License

MIT License — free for educational and personal use.
