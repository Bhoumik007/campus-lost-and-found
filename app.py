"""
Campus Lost & Found Portal — FindIt
====================================
A modern, Instagram-inspired lost-and-found platform for college campuses.
Built with Streamlit · SQLite · Perceptual Hashing · Smart Matching

Author: Ayush Sibal
"""

import streamlit as st
import sqlite3
import base64
import io
import os
import re
import json
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from difflib import SequenceMatcher

try:
    from PIL import Image
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FindIt · Campus Lost & Found",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Database ───────────────────────────────────────────────────────────────
DB_PATH = "findit.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL CHECK(type IN ('lost', 'found')),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        date_occurred TEXT NOT NULL,
        date_posted TEXT NOT NULL,
        photo BLOB,
        photo_hash TEXT,
        poster_name TEXT NOT NULL,
        poster_email TEXT NOT NULL,
        poster_phone TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'open',
        matched_with TEXT DEFAULT NULL,
        tags TEXT DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS claims (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL,
        claimer_name TEXT NOT NULL,
        claimer_email TEXT NOT NULL,
        claimer_phone TEXT DEFAULT '',
        message TEXT NOT NULL,
        proof_description TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        date_claimed TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES items(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'match',
        read INTEGER DEFAULT 0,
        date_created TEXT NOT NULL,
        related_item_id TEXT DEFAULT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
    CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
    CREATE INDEX IF NOT EXISTS idx_claims_item ON claims(item_id);
    CREATE INDEX IF NOT EXISTS idx_notif_email ON notifications(recipient_email);
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Constants ──────────────────────────────────────────────────────────────
CATEGORIES = [
    "📱 Electronics", "👛 Wallet / Purse", "🔑 Keys", "🎒 Bag / Backpack",
    "📚 Books / Notes", "👓 Eyewear", "💧 Water Bottle", "🧥 Clothing",
    "💳 ID Card / Documents", "🎧 Headphones / Earbuds", "⌚ Watch / Jewelry",
    "🔌 Charger / Cable", "🏷️ Other"
]
LOCATIONS = [
    "📚 Library", "🍽️ Cafeteria / Food Court", "🏛️ Main Building",
    "🧪 Science Block", "💻 Computer Lab", "🏟️ Sports Complex",
    "🎭 Auditorium", "🌳 Campus Garden / Quad", "🚌 Bus Stop / Parking",
    "🏢 Admin Office", "📖 Lecture Hall A", "📖 Lecture Hall B",
    "📖 Lecture Hall C", "🏠 Hostel Area", "☕ Canteen", "🗺️ Other"
]

# ─── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Playfair+Display:wght@700&display=swap');
:root {
    --primary: #6C5CE7; --primary-light: #A29BFE; --accent: #00CEC9;
    --success: #00B894; --warning: #FDCB6E; --danger: #E17055;
    --bg-card: #FFFFFF; --text-primary: #2D3436; --text-secondary: #636E72;
    --text-muted: #B2BEC3; --border: #E8E8E8;
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
    --radius-md: 12px; --radius-lg: 16px;
}
.stApp {
    background: linear-gradient(180deg, #F8F9FE 0%, #FAFAFA 100%) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
#MainMenu, footer, header {visibility: hidden;}
.stDeployButton {display: none;}
div[data-testid="stToolbar"] {display: none;}
div[data-testid="stDecoration"] {display: none;}
.stApp > header {display: none;}

.nav-bar {
    background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 50%, #74B9FF 100%);
    padding: 0.8rem 2rem; margin: -1rem -1rem 1.5rem -1rem;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 4px 20px rgba(108,92,231,0.3);
    border-radius: 0 0 20px 20px;
}
.nav-brand h1 {
    color: white; font-family: 'Playfair Display', serif;
    font-size: 1.8rem; margin: 0; font-weight: 700;
}
.nav-subtitle { color: rgba(255,255,255,0.85); font-size: 0.8rem; letter-spacing: 1.5px; text-transform: uppercase; }
.nav-stats { display: flex; gap: 1.5rem; }
.nav-stat { text-align: center; color: white; }
.nav-stat-number { font-size: 1.3rem; font-weight: 700; }
.nav-stat-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.8; }

.stTabs [data-baseweb="tab-list"] {
    background: white; border-radius: var(--radius-lg); padding: 6px;
    box-shadow: var(--shadow-md); gap: 4px; margin-bottom: 1.5rem; border: none;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-md); padding: 10px 20px;
    font-weight: 600; font-size: 0.9rem; color: var(--text-secondary); border: none;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%) !important;
    color: white !important; box-shadow: 0 4px 12px rgba(108,92,231,0.3);
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

.card-box {
    background: white; border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md); border: 1px solid var(--border);
    padding: 16px; margin-bottom: 12px;
}
.card-header-row {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
}
.card-avatar {
    width: 38px; height: 38px; border-radius: 50%;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    display: inline-flex; align-items: center; justify-content: center;
    color: white; font-weight: 700; font-size: 0.85rem; margin-right: 10px;
    vertical-align: middle;
}
.badge-lost {
    background: #FFF3E0; color: #E65100; border: 1px solid #FFCC80;
    padding: 3px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.badge-found {
    background: #E8F5E9; color: #2E7D32; border: 1px solid #A5D6A7;
    padding: 3px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.meta-chip {
    padding: 4px 10px; background: #F5F5F5; border-radius: 20px;
    font-size: 0.75rem; color: var(--text-secondary);
    display: inline-block; margin: 2px 4px 2px 0;
}
.match-bar-bg { background: #F0F0F0; border-radius: 10px; height: 8px; overflow: hidden; margin: 6px 0; }
.match-bar-fill { height: 100%; border-radius: 10px; }
.score-high { background: linear-gradient(90deg, #00B894, #55EFC4); }
.score-med { background: linear-gradient(90deg, #FDCB6E, #F39C12); }
.score-low { background: linear-gradient(90deg, #E17055, #D63031); }

.claim-card { background: white; border-radius: var(--radius-md); padding: 16px; border-left: 4px solid var(--primary); box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 10px; }
.claim-card.accepted { border-left-color: var(--success); background: #F0FFF4; }
.claim-card.rejected { border-left-color: var(--danger); background: #FFF5F5; opacity: 0.7; }

.hero-section {
    background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 40%, #74B9FF 100%);
    border-radius: 24px; padding: 3rem 2.5rem; text-align: center;
    color: white; margin-bottom: 2rem; box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}
.hero-title { font-family: 'Playfair Display', serif; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
.hero-sub { font-size: 1.1rem; opacity: 0.9; margin-bottom: 1.5rem; }

.notif-badge {
    background: var(--danger); color: white; border-radius: 50%;
    width: 20px; height: 20px; font-size: 0.7rem;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; position: relative; top: -8px; left: -4px;
}
.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    border-radius: var(--radius-md) !important; border: 2px solid var(--border) !important;
    padding: 12px 16px !important; font-size: 0.95rem !important;
}
.stButton > button {
    border-radius: var(--radius-md) !important; font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important; border: none !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important; color: white !important;
}
.fancy-divider { height: 3px; background: linear-gradient(90deg, transparent, var(--primary-light), transparent); border: none; margin: 1.5rem 0; border-radius: 2px; }

@media (max-width: 768px) {
    .nav-bar { padding: 0.6rem 1rem; flex-direction: column; gap: 8px; }
    .hero-title { font-size: 1.8rem; }
    .hero-section { padding: 2rem 1.5rem; }
}
</style>
""", unsafe_allow_html=True)

# ─── Helpers ────────────────────────────────────────────────────────────────
def gen_id():
    return uuid.uuid4().hex[:12]

def time_ago(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
        diff = datetime.now() - dt
        if diff.days > 30: return dt.strftime("%b %d, %Y")
        elif diff.days > 0: return f"{diff.days}d ago"
        elif diff.seconds > 3600: return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60: return f"{diff.seconds // 60}m ago"
        else: return "Just now"
    except:
        return date_str

def get_initials(name):
    parts = name.strip().split()
    if len(parts) >= 2: return (parts[0][0] + parts[1][0]).upper()
    elif parts: return parts[0][:2].upper()
    return "??"

def compute_image_hash(image_bytes):
    if not IMAGEHASH_AVAILABLE or not image_bytes:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return str(imagehash.phash(img))
    except:
        return ""

def image_hash_similarity(hash1, hash2):
    if not hash1 or not hash2 or not IMAGEHASH_AVAILABLE:
        return 0.0
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return max(0, 1 - ((h1 - h2) / 64))
    except:
        return 0.0

# ─── Matching Engine ────────────────────────────────────────────────────────
def text_similarity(a, b):
    if not a or not b: return 0.0
    a_lower, b_lower = a.lower().strip(), b.lower().strip()
    seq_score = SequenceMatcher(None, a_lower, b_lower).ratio()
    tokens_a = set(re.findall(r'\w+', a_lower))
    tokens_b = set(re.findall(r'\w+', b_lower))
    if not tokens_a or not tokens_b: return seq_score
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return 0.5 * seq_score + 0.5 * jaccard

def compute_match_score(lost, found):
    score = 0.0
    if lost['category'] == found['category']: score += 0.25
    score += 0.20 * text_similarity(lost['title'], found['title'])
    score += 0.15 * text_similarity(lost['description'], found['description'])
    if lost['location'] == found['location']: score += 0.15
    else: score += 0.15 * text_similarity(lost['location'], found['location']) * 0.5
    try:
        d1 = datetime.fromisoformat(lost['date_occurred'])
        d2 = datetime.fromisoformat(found['date_occurred'])
        days_diff = abs((d1 - d2).days)
        if days_diff <= 7: score += 0.10 * (1 - days_diff / 7)
    except: pass
    score += 0.15 * image_hash_similarity(lost.get('photo_hash', ''), found.get('photo_hash', ''))
    return round(score, 3)

def find_matches(item_id, top_n=5):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return []
    opposite = 'found' if item['type'] == 'lost' else 'lost'
    candidates = conn.execute("SELECT * FROM items WHERE type = ? AND status = 'open'", (opposite,)).fetchall()
    conn.close()
    item_dict = dict(item)
    scored = []
    for c in candidates:
        cd = dict(c)
        s = compute_match_score(item_dict, cd)
        if s > 0.10:
            scored.append((cd, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]

# ─── Notifications ──────────────────────────────────────────────────────────
def create_notification(email, subject, body, ntype="match", item_id=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO notifications (id, recipient_email, subject, body, type, date_created, related_item_id) VALUES (?,?,?,?,?,?,?)",
        (gen_id(), email, subject, body, ntype, datetime.now().isoformat(), item_id)
    )
    conn.commit(); conn.close()

def send_email_notification(to_email, subject, body):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if not all([smtp_host, smtp_user, smtp_pass]): return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"FindIt Campus <{smtp_user}>"
        msg['To'] = to_email
        html = f"""<div style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:20px;">
        <div style="background:linear-gradient(135deg,#6C5CE7,#A29BFE);padding:20px;border-radius:16px 16px 0 0;text-align:center;">
        <h1 style="color:white;margin:0;">FindIt</h1></div>
        <div style="background:white;padding:24px;border:1px solid #eee;border-radius:0 0 16px 16px;">
        <h2 style="color:#2D3436;">{subject}</h2><p style="color:#636E72;">{body}</p></div></div>"""
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls(); s.login(smtp_user, smtp_pass); s.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except: return False

def get_notifications(email):
    conn = get_db()
    rows = conn.execute("SELECT * FROM notifications WHERE recipient_email = ? ORDER BY date_created DESC LIMIT 20", (email,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def count_unread(email):
    conn = get_db()
    c = conn.execute("SELECT COUNT(*) FROM notifications WHERE recipient_email = ? AND read = 0", (email,)).fetchone()[0]
    conn.close(); return c

def mark_notifications_read(email):
    conn = get_db()
    conn.execute("UPDATE notifications SET read = 1 WHERE recipient_email = ?", (email,))
    conn.commit(); conn.close()

# ─── Seed Data ──────────────────────────────────────────────────────────────
def seed_data():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] > 0:
        conn.close(); return
    now = datetime.now()
    seeds = [
        ("lost", "Black Leather Wallet", "Lost my black leather wallet near the cafeteria. Has my student ID, debit card, and about Rs 500 cash. Initials 'RS' embossed.", "👛 Wallet / Purse", "🍽️ Cafeteria / Food Court", 1, "Rahul Sharma", "rahul.sharma@campus.edu"),
        ("found", "Brown Wallet with Student ID", "Found a brown/dark leather wallet on the floor near Table 7 in the cafeteria. Contains a student ID card and some cash.", "👛 Wallet / Purse", "🍽️ Cafeteria / Food Court", 1, "Priya Patel", "priya.patel@campus.edu"),
        ("lost", "Apple AirPods Pro (White Case)", "Left my AirPods Pro in the library, probably at the 2nd floor study desks near the window. White case with a small scratch on the back.", "🎧 Headphones / Earbuds", "📚 Library", 2, "Ananya Krishnan", "ananya.k@campus.edu"),
        ("found", "White AirPods Case Found in Library", "Found white AirPods Pro case under a desk on the 2nd floor of the library. Has a small scratch. Left it with the librarian.", "🎧 Headphones / Earbuds", "📚 Library", 2, "Vikram Desai", "vikram.d@campus.edu"),
        ("lost", "Blue Hydroflask Water Bottle", "Left my navy blue Hydroflask (32oz) in Lecture Hall B after morning economics class. Has stickers — a sunflower and a mountain.", "💧 Water Bottle", "📖 Lecture Hall B", 3, "Meera Joshi", "meera.j@campus.edu"),
        ("found", "Set of Keys with Honda Keychain", "Found a set of 4 keys on a Honda keychain near the main building entrance. One looks like a hostel room key.", "🔑 Keys", "🏛️ Main Building", 1, "Arjun Mehta", "arjun.m@campus.edu"),
        ("lost", "Ray-Ban Sunglasses (Aviator)", "Lost my Ray-Ban aviator sunglasses between the sports complex and parking. Gold frame, green lenses, in a brown leather case.", "👓 Eyewear", "🏟️ Sports Complex", 4, "Kavya Reddy", "kavya.r@campus.edu"),
        ("found", "TI-84 Scientific Calculator", "Found a TI-84 Plus calculator left behind in Computer Lab after data structures. Name 'Nikhil' written on the back in marker.", "📱 Electronics", "💻 Computer Lab", 2, "Sneha Gupta", "sneha.g@campus.edu"),
        ("lost", "College ID Card — Nikhil Bansal", "Lost my college ID card. Name: Nikhil Bansal, Roll No: 2024BCS045. Dropped it around admin office or canteen area.", "💳 ID Card / Documents", "🏢 Admin Office", 1, "Nikhil Bansal", "nikhil.b@campus.edu"),
        ("found", "Student ID Card Found at Canteen", "Found a student ID card on the floor of the canteen. Belongs to someone from 2024 batch, BCS stream. Left at canteen counter.", "💳 ID Card / Documents", "☕ Canteen", 1, "Tanvi Shah", "tanvi.s@campus.edu"),
        ("lost", "MacBook Charger (USB-C, 67W)", "Left my MacBook charger plugged in at the library charging station (ground floor). 67W USB-C Apple charger with braided cable.", "🔌 Charger / Cable", "📚 Library", 5, "Rohan Iyer", "rohan.i@campus.edu"),
        ("found", "North Face Backpack (Grey)", "Found a grey North Face backpack left on a bench near the campus garden. Contains notebooks and a pencil case. No name tag.", "🎒 Bag / Backpack", "🌳 Campus Garden / Quad", 3, "Aisha Khan", "aisha.k@campus.edu"),
        ("lost", "Silver Casio Watch", "Lost my silver Casio digital watch in the sports complex locker room. Silver metal band, blue digital display. Sentimental — a gift.", "⌚ Watch / Jewelry", "🏟️ Sports Complex", 2, "Dev Kapoor", "dev.k@campus.edu"),
        ("found", "Prescription Glasses (Black Frame)", "Found black rectangular prescription glasses on a seat in the auditorium after cultural fest rehearsal. In a grey hard case.", "👓 Eyewear", "🎭 Auditorium", 1, "Riya Verma", "riya.v@campus.edu"),
    ]
    for s in seeds:
        conn.execute(
            "INSERT INTO items (id,type,title,description,category,location,date_occurred,date_posted,photo,photo_hash,poster_name,poster_email,poster_phone,status,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (gen_id(), s[0], s[1], s[2], s[3], s[4],
             (now - timedelta(days=s[5])).strftime("%Y-%m-%d"),
             (now - timedelta(hours=abs(hash(s[1])) % 48)).isoformat(),
             None, "", s[6], s[7], "", "open", "[]")
        )
    conn.commit(); conn.close()

seed_data()

# ─── Session State ──────────────────────────────────────────────────────────
for key, default in [("user_email", ""), ("user_name", ""), ("logged_in", False),
                     ("active_item_detail", None), ("show_claim_form", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── CARD RENDERING (Streamlit-native — no raw HTML blobs) ─────────────────
def render_card(item, show_actions=True):
    """Render an item card using Streamlit-native components mixed with simple HTML."""
    badge_class = "badge-lost" if item['type'] == 'lost' else "badge-found"
    badge_text = "LOST" if item['type'] == 'lost' else "FOUND"
    initials = get_initials(item['poster_name'])
    posted = time_ago(item['date_posted'])

    # Card container open + header
    st.markdown(f"""<div class="card-box"><div class="card-header-row">
    <div><span class="card-avatar">{initials}</span>
    <strong style="font-size:0.9rem;">{item['poster_name']}</strong>
    <span style="color:#B2BEC3;font-size:0.75rem;margin-left:6px;">{posted}</span></div>
    <span class="{badge_class}">{badge_text}</span></div>""", unsafe_allow_html=True)

    # Photo — use st.image (Streamlit-native, always works)
    if item.get('photo') and item['photo'] is not None:
        photo_bytes = item['photo'] if isinstance(item['photo'], bytes) else base64.b64decode(item['photo'])
        st.image(photo_bytes, use_container_width=True)
    else:
        # Simple colored placeholder — no complex divs
        cat_emoji = item['category'].split()[0] if item['category'] else "📦"
        st.markdown(
            f'<div style="background:#F0F0F0;border-radius:8px;padding:2.5rem;text-align:center;'
            f'font-size:3rem;margin-bottom:8px;">{cat_emoji}</div>',
            unsafe_allow_html=True
        )

    # Body: title, description, meta chips
    desc_preview = item['description'][:150] + ('...' if len(item['description']) > 150 else '')
    status_color = {"open": "#6C5CE7", "matched": "#FDCB6E", "returned": "#00B894", "closed": "#B2BEC3"}.get(item['status'], "#B2BEC3")
    st.markdown(f"""
    <strong style="font-size:1.05rem;">{item['title']}</strong><br>
    <span style="font-size:0.88rem;color:#636E72;line-height:1.5;">{desc_preview}</span>
    <div style="margin-top:10px;">
    <span class="meta-chip">📍 {item['location']}</span>
    <span class="meta-chip">📅 {item['date_occurred']}</span>
    <span class="meta-chip">{item['category']}</span>
    <span class="meta-chip" style="color:{status_color};">● {item['status'].title()}</span>
    </div></div>""", unsafe_allow_html=True)


# ─── Onboarding ─────────────────────────────────────────────────────────────
def render_onboarding():
    st.markdown("""<div class="hero-section">
    <div class="hero-title">🔍 FindIt</div>
    <div class="hero-sub">Your campus lost &amp; found — reimagined</div>
    </div>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome to FindIt 👋")
        st.markdown("Enter your name and campus email to get started.  \nNo password needed — just so people can reach you about your items.")
        with st.form("onboarding_form"):
            name = st.text_input("Your Name", placeholder="e.g., Ayush Sibal")
            email = st.text_input("Campus Email", placeholder="e.g., ayush@campus.edu")
            submitted = st.form_submit_button("Get Started →", use_container_width=True, type="primary")
            if submitted:
                if not name.strip():
                    st.error("Please enter your name.")
                elif not email.strip() or "@" not in email:
                    st.error("Please enter a valid email address.")
                else:
                    st.session_state.user_name = name.strip()
                    st.session_state.user_email = email.strip().lower()
                    st.session_state.logged_in = True
                    st.rerun()
        st.caption("🔒 We only use your email for item notifications. No spam, ever.")


# ─── Nav Bar ────────────────────────────────────────────────────────────────
def render_nav():
    conn = get_db()
    lost = conn.execute("SELECT COUNT(*) FROM items WHERE type='lost' AND status='open'").fetchone()[0]
    found = conn.execute("SELECT COUNT(*) FROM items WHERE type='found' AND status='open'").fetchone()[0]
    returned = conn.execute("SELECT COUNT(*) FROM items WHERE status='returned'").fetchone()[0]
    conn.close()
    st.markdown(f"""<div class="nav-bar">
    <div><h1 style="color:white;font-family:'Playfair Display',serif;font-size:1.8rem;margin:0;">🔍 FindIt</h1>
    <div class="nav-subtitle">Campus Lost &amp; Found</div></div>
    <div class="nav-stats">
    <div class="nav-stat"><div class="nav-stat-number">{lost}</div><div class="nav-stat-label">Lost</div></div>
    <div class="nav-stat"><div class="nav-stat-number">{found}</div><div class="nav-stat-label">Found</div></div>
    <div class="nav-stat"><div class="nav-stat-number">{returned}</div><div class="nav-stat-label">Reunited ✨</div></div>
    </div></div>""", unsafe_allow_html=True)


# ─── Feed ───────────────────────────────────────────────────────────────────
def render_feed():
    st.markdown("### 📰 Live Feed")
    fc1, fc2, fc3, fc4 = st.columns([1,1,1,1])
    with fc1: type_f = st.selectbox("Type", ["All","Lost","Found"], key="ft")
    with fc2: cat_f = st.selectbox("Category", ["All"] + CATEGORIES, key="fc")
    with fc3: loc_f = st.selectbox("Location", ["All"] + LOCATIONS, key="fl")
    with fc4: search_q = st.text_input("🔍 Search", placeholder="Search items...", key="fs")

    query, params = "SELECT * FROM items WHERE 1=1", []
    if type_f != "All": query += " AND type=?"; params.append(type_f.lower())
    if cat_f != "All": query += " AND category=?"; params.append(cat_f)
    if loc_f != "All": query += " AND location=?"; params.append(loc_f)
    if search_q.strip(): query += " AND (title LIKE ? OR description LIKE ?)"; params.extend([f"%{search_q}%"]*2)
    query += " ORDER BY date_posted DESC"

    conn = get_db()
    items = conn.execute(query, params).fetchall()
    conn.close()

    if not items:
        st.info("🔍 No items found matching your filters.")
        return

    cols = st.columns(2)
    for idx, item in enumerate(items):
        d = dict(item)
        with cols[idx % 2]:
            render_card(d)
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("🔎 Details", key=f"det_{d['id']}", use_container_width=True):
                    st.session_state.active_item_detail = d['id']; st.rerun()
            with bc2:
                if d['status'] == 'open' and d['poster_email'] != st.session_state.user_email:
                    lbl = "🙋 This is Mine!" if d['type'] == 'found' else "✋ I Found This!"
                    if st.button(lbl, key=f"clm_{d['id']}", use_container_width=True, type="primary"):
                        st.session_state.show_claim_form = d['id']
                        st.session_state.active_item_detail = d['id']; st.rerun()


# ─── Post ───────────────────────────────────────────────────────────────────
def render_post():
    st.markdown("### 📝 Post an Item")
    st.info("💡 **Tip:** Add as much detail as possible — color, brand, distinguishing marks. A photo boosts match chances by 3x!")

    with st.form("post_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            item_type = st.radio("What are you posting?", ["🔴 I Lost Something", "🟢 I Found Something"], horizontal=True)
            resolved_type = "lost" if "Lost" in item_type else "found"
            title = st.text_input("Item Title *", placeholder="e.g., Black Leather Wallet with Initials 'RS'")
            category = st.selectbox("Category *", CATEGORIES)
            location = st.selectbox("Location *", LOCATIONS)
        with c2:
            date_occurred = st.date_input("When did you lose/find it? *", value=datetime.now().date(), max_value=datetime.now().date())
            description = st.text_area("Description *", placeholder="Color, brand, size, identifying marks, where exactly...", height=130)
            photo = st.file_uploader("📷 Upload a Photo (recommended)", type=["jpg","jpeg","png","webp"])
        phone = st.text_input("Phone (optional — for WhatsApp notifications)", placeholder="+91-9876543210")
        submitted = st.form_submit_button("🚀 Post Item", use_container_width=True, type="primary")

        if submitted:
            if not title.strip(): st.error("Please enter an item title."); return
            if not description.strip(): st.error("Please add a description."); return

            photo_bytes, photo_hash = None, ""
            if photo is not None:
                photo_bytes = photo.read()
                photo_hash = compute_image_hash(photo_bytes)

            item_id = gen_id()
            conn = get_db()
            conn.execute(
                "INSERT INTO items (id,type,title,description,category,location,date_occurred,date_posted,photo,photo_hash,poster_name,poster_email,poster_phone,status,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, resolved_type, title.strip(), description.strip(), category, location,
                 date_occurred.isoformat(), datetime.now().isoformat(), photo_bytes, photo_hash,
                 st.session_state.user_name, st.session_state.user_email, phone.strip(), "open", "[]")
            )
            conn.commit(); conn.close()

            # Auto-match
            matches = find_matches(item_id, top_n=3)
            for m_item, score in matches:
                if score >= 0.25:
                    pct = int(score * 100)
                    create_notification(st.session_state.user_email, f"🎯 Potential Match ({pct}%)",
                        f"Your item '{title}' may match '{m_item['title']}' by {m_item['poster_name']}.", "match", item_id)
                    create_notification(m_item['poster_email'], f"🎯 Potential Match ({pct}%)",
                        f"New item '{title}' by {st.session_state.user_name} may match your '{m_item['title']}'.", "match", m_item['id'])
                    send_email_notification(m_item['poster_email'], f"FindIt: Match for '{m_item['title']}'",
                        f"A new item '{title}' matches your listing with {pct}% confidence. Check FindIt!")

            st.success("🎉 Item posted successfully!")
            if matches and matches[0][1] >= 0.25:
                st.info(f"✨ Found {len([m for m in matches if m[1] >= 0.25])} potential match(es)! Check the Matches tab.")
            st.balloons()


# ─── Matches ────────────────────────────────────────────────────────────────
def render_matches():
    st.markdown("### 🎯 Smart Matches")
    st.markdown("""<div style="background:linear-gradient(135deg,#6C5CE7,#A29BFE);border-radius:12px;
    padding:16px 20px;margin-bottom:1.5rem;color:white;font-size:0.9rem;">
    <strong>How matching works:</strong> We compare category, title, description, location, date proximity,
    and image similarity (perceptual hashing) to find probable matches.</div>""", unsafe_allow_html=True)

    conn = get_db()
    my_items = conn.execute("SELECT * FROM items WHERE poster_email=? AND status='open' ORDER BY date_posted DESC",
                            (st.session_state.user_email,)).fetchall()
    all_open = conn.execute("SELECT * FROM items WHERE status='open' ORDER BY date_posted DESC").fetchall()
    conn.close()

    if my_items:
        st.markdown("#### 🔗 Matches for Your Items")
        for item in my_items:
            d = dict(item)
            matches = find_matches(d['id'], top_n=5)
            emoji = "🔴" if d['type'] == 'lost' else "🟢"
            with st.expander(f"{emoji} {d['title']} — {len(matches)} match(es)"):
                if not matches:
                    st.write("No matches yet. Check back as new items are posted!")
                for m_item, score in matches:
                    pct = int(score * 100)
                    bar_class = "score-high" if pct >= 60 else "score-med" if pct >= 35 else "score-low"
                    color = "#00B894" if pct >= 60 else "#FDCB6E" if pct >= 35 else "#E17055"
                    st.markdown(f"""<div class="card-box">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong>{m_item['title']}</strong>
                    <span style="font-weight:700;color:{color};">{pct}% match</span></div>
                    <div class="match-bar-bg"><div class="match-bar-fill {bar_class}" style="width:{pct}%;"></div></div>
                    <span style="font-size:0.85rem;color:#636E72;">{m_item['description'][:120]}...</span><br>
                    <span class="meta-chip">📍 {m_item['location']}</span>
                    <span class="meta-chip">👤 {m_item['poster_name']}</span></div>""", unsafe_allow_html=True)
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("View", key=f"mv_{d['id']}_{m_item['id']}", use_container_width=True):
                            st.session_state.active_item_detail = m_item['id']; st.rerun()
                    with b2:
                        lbl = "🙋 Mine!" if m_item['type'] == 'found' else "✋ I Found This!"
                        if st.button(lbl, key=f"mc_{d['id']}_{m_item['id']}", use_container_width=True, type="primary"):
                            st.session_state.show_claim_form = m_item['id']
                            st.session_state.active_item_detail = m_item['id']; st.rerun()
    else:
        st.info("Post an item to see smart matches here!")

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### 🌐 Match Explorer")
    if all_open:
        opts = {f"{dict(i)['type'].upper()}: {dict(i)['title']}": dict(i)['id'] for i in all_open}
        sel = st.selectbox("Pick an item", list(opts.keys()), key="mex")
        if sel:
            for m_item, score in find_matches(opts[sel], top_n=5):
                pct = int(score * 100)
                color = "#00B894" if pct >= 60 else "#FDCB6E" if pct >= 35 else "#E17055"
                bar_class = "score-high" if pct >= 60 else "score-med" if pct >= 35 else "score-low"
                st.markdown(f"""<div class="card-box">
                <div style="display:flex;justify-content:space-between;"><strong>{m_item['title']}</strong>
                <span style="font-weight:700;color:{color};">{pct}%</span></div>
                <div class="match-bar-bg"><div class="match-bar-fill {bar_class}" style="width:{pct}%;"></div></div>
                <span style="font-size:0.85rem;color:#636E72;">{m_item['description'][:100]}...</span><br>
                <span class="meta-chip">📍 {m_item['location']}</span>
                <span class="meta-chip">👤 {m_item['poster_name']}</span></div>""", unsafe_allow_html=True)


# ─── Item Detail + Claims ──────────────────────────────────────────────────
def render_item_detail():
    item_id = st.session_state.active_item_detail
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        st.error("Item not found."); conn.close(); return
    d = dict(item)
    claims = [dict(c) for c in conn.execute("SELECT * FROM claims WHERE item_id=? ORDER BY date_claimed DESC", (item_id,)).fetchall()]
    conn.close()

    if st.button("← Back to Feed"):
        st.session_state.active_item_detail = None
        st.session_state.show_claim_form = None
        st.rerun()

    render_card(d, show_actions=False)

    # Full details
    st.markdown("**📋 Full Description**")
    st.write(d['description'])
    contact_info = f"📧 {d['poster_email']}"
    if d.get('poster_phone'):
        contact_info += f"  ·  📱 {d['poster_phone']}"
    st.caption(contact_info)

    # Matches
    matches = find_matches(item_id, top_n=3)
    if matches:
        st.markdown("#### 🎯 Potential Matches")
        for m_item, score in matches:
            pct = int(score * 100)
            st.markdown(f"""<div style="background:#F9F9FF;border-radius:10px;padding:12px 16px;margin-bottom:8px;border-left:3px solid #6C5CE7;">
            <strong>{m_item['title']}</strong> — <span style="color:#6C5CE7;font-weight:600;">{pct}% match</span><br>
            <span style="font-size:0.85rem;color:#636E72;">by {m_item['poster_name']} · {m_item['location']}</span></div>""", unsafe_allow_html=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # Claim section
    is_poster = d['poster_email'] == st.session_state.user_email
    already_claimed = any(c['claimer_email'] == st.session_state.user_email for c in claims)

    if d['status'] == 'open' and not is_poster and not already_claimed:
        lbl = "🙋 Claim: This is My Item!" if d['type'] == 'found' else "✋ Claim: I Found This Item!"
        if st.button(lbl, type="primary", use_container_width=True, key="det_claim"):
            st.session_state.show_claim_form = item_id

    if st.session_state.show_claim_form == item_id:
        st.markdown("**📋 Submit Your Claim**")
        st.caption("Describe why this is your item. Include identifying details the poster didn't mention.")
        with st.form("claim_form", clear_on_submit=True):
            claim_msg = st.text_area("Your Claim Message *", placeholder="This is my wallet — it has a Starbucks card inside...", height=100)
            proof = st.text_area("Proof of Ownership (details only the owner would know)", placeholder="Torn receipt from Chai Point in front pocket", height=80)
            cphone = st.text_input("Your Phone (optional)", placeholder="+91-9876543210")
            if st.form_submit_button("Submit Claim", type="primary", use_container_width=True):
                if not claim_msg.strip():
                    st.error("Please describe why this item is yours.")
                else:
                    cid = gen_id()
                    conn2 = get_db()
                    conn2.execute("INSERT INTO claims (id,item_id,claimer_name,claimer_email,claimer_phone,message,proof_description,status,date_claimed) VALUES (?,?,?,?,?,?,?,?,?)",
                        (cid, item_id, st.session_state.user_name, st.session_state.user_email, cphone.strip(), claim_msg.strip(), proof.strip(), "pending", datetime.now().isoformat()))
                    conn2.commit(); conn2.close()
                    create_notification(d['poster_email'], f"🙋 New Claim on '{d['title']}'",
                        f"{st.session_state.user_name} claimed your item. Review in My Items.", "claim", item_id)
                    send_email_notification(d['poster_email'], f"FindIt: Claim on '{d['title']}'",
                        f"{st.session_state.user_name} submitted a claim on your item. Log in to review.")
                    st.success("✅ Claim submitted! The poster will be notified.")
                    st.session_state.show_claim_form = None; st.rerun()

    # Poster's claim management
    if is_poster and claims:
        st.markdown(f"#### 📬 Claims on Your Item ({len(claims)})")
        for claim in claims:
            status_colors = {"pending": "#6C5CE7", "accepted": "#00B894", "rejected": "#E17055"}
            card_cls = claim['status']
            st.markdown(f"""<div class="claim-card {card_cls}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div><strong>{claim['claimer_name']}</strong>
            <span style="color:#B2BEC3;font-size:0.8rem;"> · {claim['claimer_email']}</span></div>
            <span style="background:{status_colors.get(claim['status'],'#B2BEC3')};color:white;padding:2px 10px;border-radius:12px;font-size:0.7rem;font-weight:600;">{claim['status'].upper()}</span></div>
            <p style="color:#636E72;font-size:0.9rem;margin:4px 0;">{claim['message']}</p>
            {"<p style='color:#6C5CE7;font-size:0.85rem;'><strong>Proof:</strong> " + claim['proof_description'] + "</p>" if claim.get('proof_description') else ""}
            <span style="font-size:0.75rem;color:#B2BEC3;">Claimed {time_ago(claim['date_claimed'])}</span></div>""", unsafe_allow_html=True)

            if claim['status'] == 'pending':
                ca, cr = st.columns(2)
                with ca:
                    if st.button("✅ Accept", key=f"acc_{claim['id']}", use_container_width=True, type="primary"):
                        conn3 = get_db()
                        conn3.execute("UPDATE claims SET status='accepted' WHERE id=?", (claim['id'],))
                        conn3.execute("UPDATE claims SET status='rejected' WHERE item_id=? AND id!=? AND status='pending'", (item_id, claim['id']))
                        conn3.execute("UPDATE items SET status='returned', matched_with=? WHERE id=?", (claim['claimer_email'], item_id))
                        conn3.commit(); conn3.close()
                        create_notification(claim['claimer_email'], f"🎉 Claim Accepted!",
                            f"Your claim on '{d['title']}' was accepted! Contact {d['poster_name']} at {d['poster_email']}.", "claim_accepted", item_id)
                        send_email_notification(claim['claimer_email'], f"FindIt: Claim accepted!",
                            f"Great news! Your claim on '{d['title']}' was accepted. Contact {d['poster_email']} to get it back!")
                        st.success("Claim accepted!"); st.rerun()
                with cr:
                    if st.button("❌ Reject", key=f"rej_{claim['id']}", use_container_width=True):
                        conn3 = get_db()
                        conn3.execute("UPDATE claims SET status='rejected' WHERE id=?", (claim['id'],))
                        conn3.commit(); conn3.close()
                        create_notification(claim['claimer_email'], f"Claim Not Accepted",
                            f"Your claim on '{d['title']}' was not accepted.", "claim_rejected", item_id)
                        st.warning("Claim rejected."); st.rerun()

    elif is_poster and not claims:
        st.info("No claims yet. We'll notify you when someone claims this item.")


# ─── My Items ──────────────────────────────────────────────────────────────
def render_my_items():
    st.markdown("### 📦 My Items")
    conn = get_db()
    my_items = conn.execute("SELECT * FROM items WHERE poster_email=? ORDER BY date_posted DESC", (st.session_state.user_email,)).fetchall()
    my_claims = conn.execute(
        "SELECT c.*, i.title as item_title, i.type as item_type, i.poster_name as item_poster FROM claims c JOIN items i ON c.item_id=i.id WHERE c.claimer_email=? ORDER BY c.date_claimed DESC",
        (st.session_state.user_email,)).fetchall()
    conn.close()

    t1, t2 = st.tabs(["📮 My Posts", "🙋 My Claims"])
    with t1:
        if not my_items:
            st.info("You haven't posted any items yet.")
        for item in my_items:
            d = dict(item)
            conn2 = get_db()
            total_claims = conn2.execute("SELECT COUNT(*) FROM claims WHERE item_id=?", (d['id'],)).fetchone()[0]
            pending = conn2.execute("SELECT COUNT(*) FROM claims WHERE item_id=? AND status='pending'", (d['id'],)).fetchone()[0]
            conn2.close()
            render_card(d)
            ic, ac = st.columns([2, 1])
            with ic:
                if total_claims > 0:
                    st.markdown(f"📬 **{total_claims} claim(s)** — {pending} pending")
            with ac:
                if st.button("Manage →", key=f"mng_{d['id']}", use_container_width=True, type="primary"):
                    st.session_state.active_item_detail = d['id']; st.rerun()
            st.divider()

    with t2:
        if not my_claims:
            st.info("You haven't claimed any items yet.")
        for claim in my_claims:
            c = dict(claim)
            emoji = {"pending": "⏳", "accepted": "✅", "rejected": "❌"}.get(c['status'], "")
            st.markdown(f"""<div class="claim-card {c['status']}">
            <strong>{c['item_title']}</strong>
            <span style="font-size:0.85rem;color:#B2BEC3;"> · {c['item_type'].title()} by {c['item_poster']}</span><br>
            <span>{emoji} {c['status'].title()}</span>
            <p style="color:#636E72;font-size:0.85rem;margin-top:6px;">{c['message'][:100]}...</p></div>""", unsafe_allow_html=True)


# ─── Notifications ──────────────────────────────────────────────────────────
def render_notifications():
    unread = count_unread(st.session_state.user_email)
    badge = f' <span class="notif-badge">{unread}</span>' if unread > 0 else ""
    st.markdown(f"### 🔔 Notifications{badge}", unsafe_allow_html=True)

    if st.button("Mark All as Read"):
        mark_notifications_read(st.session_state.user_email); st.rerun()

    notifs = get_notifications(st.session_state.user_email)
    if not notifs:
        st.info("No notifications yet. We'll alert you on matches and claims!")
        return
    for n in notifs:
        bg = "#F0EDFF" if not n['read'] else "white"
        border = "2px solid #6C5CE7" if not n['read'] else "1px solid #eee"
        st.markdown(f"""<div style="background:{bg};border:{border};border-radius:12px;padding:14px 18px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong style="font-size:0.95rem;">{n['subject']}</strong>
        <span style="font-size:0.75rem;color:#B2BEC3;">{time_ago(n['date_created'])}</span></div>
        <p style="color:#636E72;font-size:0.88rem;margin:6px 0 0;">{n['body']}</p></div>""", unsafe_allow_html=True)


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    if not st.session_state.logged_in:
        render_onboarding(); return

    render_nav()

    if st.session_state.active_item_detail:
        render_item_detail(); return

    with st.sidebar:
        initials = get_initials(st.session_state.user_name)
        st.markdown(f"""<div style="text-align:center;padding:1rem 0;">
        <div style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#6C5CE7,#00CEC9);
        display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:1.2rem;margin:0 auto 8px;">
        {initials}</div><strong>{st.session_state.user_name}</strong><br>
        <span style="font-size:0.8rem;color:#B2BEC3;">{st.session_state.user_email}</span></div>""", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 Switch User", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.user_email = ""; st.session_state.user_name = ""; st.rerun()
        st.divider()
        st.caption("**FindIt v1.0** · Campus Lost & Found · Built with Streamlit")

    unread = count_unread(st.session_state.user_email)
    notif_label = f"🔔 Alerts ({unread})" if unread > 0 else "🔔 Alerts"
    tab_feed, tab_post, tab_matches, tab_myitems, tab_notifs = st.tabs(["📰 Feed", "📝 Post", "🎯 Matches", "📦 My Items", notif_label])
    with tab_feed: render_feed()
    with tab_post: render_post()
    with tab_matches: render_matches()
    with tab_myitems: render_my_items()
    with tab_notifs: render_notifications()

if __name__ == "__main__":
    main()
