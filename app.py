"""
Campus Lost & Found Portal
===========================
A modern, Instagram-inspired lost-and-found platform for college campuses.
Built with Streamlit · SQLite · Perceptual Hashing · Smart Matching

Author: Ayush Sibal
"""

import streamlit as st
import sqlite3
import hashlib
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
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter

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

# ─── Database Setup ─────────────────────────────────────────────────────────
DB_PATH = "findit.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
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
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'matched', 'returned', 'closed')),
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
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
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
    CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
    CREATE INDEX IF NOT EXISTS idx_claims_item ON claims(item_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_email ON notifications(recipient_email);
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

# ─── CSS: Instagram-Inspired Design ────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    /* ── Import Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Playfair+Display:wght@700&display=swap');

    /* ── Root Variables ── */
    :root {
        --primary: #6C5CE7;
        --primary-light: #A29BFE;
        --primary-dark: #5A4BD1;
        --accent: #00CEC9;
        --accent-light: #81ECEC;
        --success: #00B894;
        --warning: #FDCB6E;
        --danger: #E17055;
        --lost-color: #E17055;
        --lost-bg: #FFEAA7;
        --found-color: #00B894;
        --found-bg: #DFFFD6;
        --bg-primary: #FAFAFA;
        --bg-card: #FFFFFF;
        --text-primary: #2D3436;
        --text-secondary: #636E72;
        --text-muted: #B2BEC3;
        --border: #E8E8E8;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
        --shadow-lg: 0 8px 30px rgba(0,0,0,0.12);
        --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 24px;
    }

    /* ── Global Reset ── */
    .stApp {
        background: linear-gradient(180deg, #F8F9FE 0%, #FAFAFA 100%) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Hide default Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    div[data-testid="stToolbar"] {display: none;}
    div[data-testid="stDecoration"] {display: none;}
    .stApp > header {display: none;}

    /* ── Top Navigation Bar ── */
    .nav-bar {
        background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 50%, #74B9FF 100%);
        padding: 0.8rem 2rem;
        margin: -1rem -1rem 1.5rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 20px rgba(108,92,231,0.3);
        position: relative;
        z-index: 100;
        border-radius: 0 0 20px 20px;
    }
    .nav-brand {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nav-brand h1 {
        color: white;
        font-family: 'Playfair Display', serif;
        font-size: 1.8rem;
        margin: 0;
        font-weight: 700;
        letter-spacing: -0.5px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .nav-brand .logo-icon {
        font-size: 2rem;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));
    }
    .nav-subtitle {
        color: rgba(255,255,255,0.85);
        font-size: 0.8rem;
        font-weight: 400;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .nav-stats {
        display: flex;
        gap: 1.5rem;
    }
    .nav-stat {
        text-align: center;
        color: white;
    }
    .nav-stat-number {
        font-size: 1.3rem;
        font-weight: 700;
    }
    .nav-stat-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.8;
    }

    /* ── Tab Navigation (Instagram-style) ── */
    .stTabs [data-baseweb="tab-list"] {
        background: white;
        border-radius: var(--radius-lg);
        padding: 6px;
        box-shadow: var(--shadow-md);
        gap: 4px;
        margin-bottom: 1.5rem;
        border: none;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-md);
        padding: 10px 20px;
        font-weight: 600;
        font-size: 0.9rem;
        color: var(--text-secondary);
        border: none;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: #F0EDFF;
        color: var(--primary);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(108,92,231,0.3);
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    /* ── Item Cards ── */
    .item-card {
        background: var(--bg-card);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-md);
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid var(--border);
        margin-bottom: 1rem;
    }
    .item-card:hover {
        transform: translateY(-3px);
        box-shadow: var(--shadow-lg);
    }
    .card-header {
        padding: 14px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #F5F5F5;
    }
    .card-poster {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .card-avatar {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .card-poster-name {
        font-weight: 600;
        font-size: 0.9rem;
        color: var(--text-primary);
    }
    .card-poster-time {
        font-size: 0.75rem;
        color: var(--text-muted);
    }
    .card-type-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-lost {
        background: #FFF3E0;
        color: #E65100;
        border: 1px solid #FFCC80;
    }
    .badge-found {
        background: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #A5D6A7;
    }
    .card-image {
        width: 100%;
        aspect-ratio: 4/3;
        object-fit: cover;
        display: block;
        background: #F5F5F5;
    }
    .card-body {
        padding: 16px 18px;
    }
    .card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 6px;
    }
    .card-desc {
        font-size: 0.88rem;
        color: var(--text-secondary);
        line-height: 1.5;
        margin-bottom: 12px;
    }
    .card-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }
    .meta-chip {
        padding: 4px 10px;
        background: #F5F5F5;
        border-radius: 20px;
        font-size: 0.75rem;
        color: var(--text-secondary);
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .card-actions {
        padding: 12px 18px;
        border-top: 1px solid #F5F5F5;
        display: flex;
        gap: 10px;
    }

    /* ── Status Badge ── */
    .status-open { color: var(--primary); }
    .status-matched { color: var(--warning); }
    .status-returned { color: var(--success); }
    .status-closed { color: var(--text-muted); }

    /* ── Match Score Bar ── */
    .match-score-container {
        background: #F0F0F0;
        border-radius: 10px;
        height: 8px;
        overflow: hidden;
        margin: 6px 0;
    }
    .match-score-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
    }
    .score-high { background: linear-gradient(90deg, #00B894, #55EFC4); }
    .score-med { background: linear-gradient(90deg, #FDCB6E, #F39C12); }
    .score-low { background: linear-gradient(90deg, #E17055, #D63031); }

    /* ── Claim Card ── */
    .claim-card {
        background: white;
        border-radius: var(--radius-md);
        padding: 16px;
        border-left: 4px solid var(--primary);
        box-shadow: var(--shadow-sm);
        margin-bottom: 10px;
    }
    .claim-card.accepted {
        border-left-color: var(--success);
        background: #F0FFF4;
    }
    .claim-card.rejected {
        border-left-color: var(--danger);
        background: #FFF5F5;
        opacity: 0.7;
    }

    /* ── Hero Section ── */
    .hero-section {
        background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 40%, #74B9FF 100%);
        border-radius: var(--radius-xl);
        padding: 3rem 2.5rem;
        text-align: center;
        color: white;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-xl);
    }
    .hero-section::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 60%);
        animation: pulse-slow 8s ease-in-out infinite;
    }
    @keyframes pulse-slow {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
    }
    .hero-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        position: relative;
        text-shadow: 0 2px 10px rgba(0,0,0,0.15);
    }
    .hero-sub {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-bottom: 1.5rem;
        position: relative;
    }
    .hero-stats {
        display: flex;
        justify-content: center;
        gap: 3rem;
        position: relative;
    }
    .hero-stat {
        text-align: center;
    }
    .hero-stat-num {
        font-size: 2rem;
        font-weight: 800;
    }
    .hero-stat-label {
        font-size: 0.8rem;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* ── Notification Bell ── */
    .notif-badge {
        background: var(--danger);
        color: white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        font-size: 0.7rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        position: relative;
        top: -8px;
        left: -4px;
    }

    /* ── Empty State ── */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        color: var(--text-muted);
    }
    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    .empty-state-text {
        font-size: 1.1rem;
        font-weight: 500;
    }

    /* ── Streamlit Form Overrides ── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: var(--radius-md) !important;
        border: 2px solid var(--border) !important;
        padding: 12px 16px !important;
        font-size: 0.95rem !important;
        transition: border-color 0.2s ease !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(108,92,231,0.1) !important;
    }
    .stSelectbox > div > div {
        border-radius: var(--radius-md) !important;
    }
    .stButton > button {
        border-radius: var(--radius-md) !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important;
        color: white !important;
    }

    /* ── Section Headers ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid #F0F0F0;
    }
    .section-header h2 {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }

    /* ── Responsive ── */
    @media (max-width: 768px) {
        .nav-bar { padding: 0.6rem 1rem; flex-direction: column; gap: 8px; }
        .nav-stats { gap: 1rem; }
        .hero-title { font-size: 1.8rem; }
        .hero-stats { gap: 1.5rem; }
        .hero-section { padding: 2rem 1.5rem; }
        .card-meta { gap: 6px; }
        .item-card { margin-bottom: 0.8rem; }
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: #D0D0D0;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover { background: #B0B0B0; }

    /* ── Animations ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: fadeInUp 0.4s ease-out;
    }

    /* ── Expander overrides ── */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border-radius: var(--radius-md) !important;
    }

    /* ── Divider ── */
    .fancy-divider {
        height: 3px;
        background: linear-gradient(90deg, transparent, var(--primary-light), transparent);
        border: none;
        margin: 1.5rem 0;
        border-radius: 2px;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Helper Functions ───────────────────────────────────────────────────────

def gen_id():
    return uuid.uuid4().hex[:12]

def time_ago(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
        diff = datetime.now() - dt
        if diff.days > 30:
            return dt.strftime("%b %d, %Y")
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except:
        return date_str

def get_initials(name):
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif parts:
        return parts[0][:2].upper()
    return "??"

def image_to_base64(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def base64_to_image_tag(b64_str, css_class="card-image"):
    return f'<img src="data:image/jpeg;base64,{b64_str}" class="{css_class}" />'

def compute_image_hash(image_bytes):
    if not IMAGEHASH_AVAILABLE:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = str(imagehash.phash(img))
        return phash
    except:
        return ""

def image_hash_similarity(hash1, hash2):
    if not hash1 or not hash2 or not IMAGEHASH_AVAILABLE:
        return 0.0
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        max_dist = 64
        dist = h1 - h2
        return max(0, 1 - (dist / max_dist))
    except:
        return 0.0


# ─── Matching Engine ────────────────────────────────────────────────────────

def text_similarity(a, b):
    """Compute text similarity using token overlap + sequence matching."""
    if not a or not b:
        return 0.0
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    seq_score = SequenceMatcher(None, a_lower, b_lower).ratio()
    tokens_a = set(re.findall(r'\w+', a_lower))
    tokens_b = set(re.findall(r'\w+', b_lower))
    if not tokens_a or not tokens_b:
        return seq_score
    overlap = len(tokens_a & tokens_b)
    jaccard = overlap / len(tokens_a | tokens_b)
    return 0.5 * seq_score + 0.5 * jaccard

def compute_match_score(lost_item, found_item):
    """
    Multi-signal match scoring:
      - Category match:    25% weight
      - Title similarity:  20% weight
      - Desc similarity:   15% weight
      - Location match:    15% weight
      - Date proximity:    10% weight
      - Image hash sim:    15% weight
    """
    score = 0.0
    # Category (exact match)
    if lost_item['category'] == found_item['category']:
        score += 0.25
    # Title
    score += 0.20 * text_similarity(lost_item['title'], found_item['title'])
    # Description
    score += 0.15 * text_similarity(lost_item['description'], found_item['description'])
    # Location
    if lost_item['location'] == found_item['location']:
        score += 0.15
    else:
        score += 0.15 * text_similarity(lost_item['location'], found_item['location']) * 0.5
    # Date proximity (within 7 days = full score, decays linearly)
    try:
        d1 = datetime.fromisoformat(lost_item['date_occurred'])
        d2 = datetime.fromisoformat(found_item['date_occurred'])
        days_diff = abs((d1 - d2).days)
        if days_diff <= 7:
            score += 0.10 * (1 - days_diff / 7)
    except:
        pass
    # Image hash similarity
    score += 0.15 * image_hash_similarity(
        lost_item.get('photo_hash', ''),
        found_item.get('photo_hash', '')
    )
    return round(score, 3)

def find_matches(item_id, top_n=5):
    conn = get_db()
    c = conn.cursor()
    item = c.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return []
    opposite_type = 'found' if item['type'] == 'lost' else 'lost'
    candidates = c.execute(
        "SELECT * FROM items WHERE type = ? AND status = 'open'",
        (opposite_type,)
    ).fetchall()
    conn.close()
    scored = []
    item_dict = dict(item)
    for cand in candidates:
        cand_dict = dict(cand)
        score = compute_match_score(item_dict, cand_dict)
        if score > 0.10:
            scored.append((cand_dict, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


# ─── Notification System ───────────────────────────────────────────────────

def create_notification(recipient_email, subject, body, notif_type="match", related_item_id=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO notifications (id, recipient_email, subject, body, type, date_created, related_item_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (gen_id(), recipient_email, subject, body, notif_type, datetime.now().isoformat(), related_item_id)
    )
    conn.commit()
    conn.close()

def send_email_notification(to_email, subject, body):
    """Attempt to send email via SMTP. Silently fails if not configured."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_email = os.environ.get("SMTP_FROM", smtp_user)
    if not all([smtp_host, smtp_user, smtp_pass]):
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"FindIt Campus <{from_email}>"
        msg['To'] = to_email
        html_body = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #6C5CE7, #A29BFE); padding: 20px; border-radius: 16px 16px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🔍 FindIt</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 4px 0 0 0; font-size: 12px;">CAMPUS LOST & FOUND</p>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #eee; border-radius: 0 0 16px 16px;">
                <h2 style="color: #2D3436; font-size: 18px;">{subject}</h2>
                <p style="color: #636E72; line-height: 1.6;">{body}</p>
                <hr style="border: none; height: 1px; background: #eee; margin: 20px 0;">
                <p style="color: #B2BEC3; font-size: 12px; text-align: center;">
                    This is an automated notification from FindIt Campus Portal.
                </p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        return True
    except:
        return False

def get_notifications(email):
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE recipient_email = ? ORDER BY date_created DESC LIMIT 20",
        (email,)
    ).fetchall()
    conn.close()
    return [dict(n) for n in notifs]

def count_unread(email):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE recipient_email = ? AND read = 0",
        (email,)
    ).fetchone()[0]
    conn.close()
    return count

def mark_notifications_read(email):
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET read = 1 WHERE recipient_email = ?",
        (email,)
    )
    conn.commit()
    conn.close()


# ─── Seed Data ──────────────────────────────────────────────────────────────

def seed_data():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if count > 0:
        conn.close()
        return
    now = datetime.now()
    seed_items = [
        {
            "id": gen_id(), "type": "lost",
            "title": "Black Leather Wallet",
            "description": "Lost my black leather wallet near the cafeteria. It has my student ID, debit card, and about ₹500 cash. The wallet has my initials 'RS' embossed on it.",
            "category": "👛 Wallet / Purse", "location": "🍽️ Cafeteria / Food Court",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Rahul Sharma", "poster_email": "rahul.sharma@campus.edu",
            "poster_phone": "+91-9876543210", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "Brown Wallet with Student ID",
            "description": "Found a brown/dark leather wallet on the floor near Table 7 in the cafeteria. Contains a student ID card and some cash. Want to return it!",
            "category": "👛 Wallet / Purse", "location": "🍽️ Cafeteria / Food Court",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Priya Patel", "poster_email": "priya.patel@campus.edu",
            "poster_phone": "+91-9876543211", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "Apple AirPods Pro (White Case)",
            "description": "Left my AirPods Pro in the library, probably at the second floor study desks near the window. White case with a small scratch on the back.",
            "category": "🎧 Headphones / Earbuds", "location": "📚 Library",
            "date_occurred": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "poster_name": "Ananya Krishnan", "poster_email": "ananya.k@campus.edu",
            "poster_phone": "", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "White AirPods Case Found in Library",
            "description": "Found white AirPods Pro case under a desk on the 2nd floor of the library. Has a small scratch on it. Left it with the librarian at the front desk.",
            "category": "🎧 Headphones / Earbuds", "location": "📚 Library",
            "date_occurred": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "poster_name": "Vikram Desai", "poster_email": "vikram.d@campus.edu",
            "poster_phone": "+91-9876543212", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "Blue Hydroflask Water Bottle",
            "description": "Left my navy blue Hydroflask (32oz) in Lecture Hall B after the morning economics class. It has stickers on it — a sunflower and a mountain.",
            "category": "💧 Water Bottle", "location": "📖 Lecture Hall B",
            "date_occurred": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "poster_name": "Meera Joshi", "poster_email": "meera.j@campus.edu",
            "poster_phone": "+91-9876543213", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "Set of Keys with Honda Keychain",
            "description": "Found a set of 4 keys on a Honda keychain near the main building entrance. One looks like a hostel room key.",
            "category": "🔑 Keys", "location": "🏛️ Main Building",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Arjun Mehta", "poster_email": "arjun.m@campus.edu",
            "poster_phone": "+91-9876543214", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "Ray-Ban Sunglasses (Aviator)",
            "description": "Lost my Ray-Ban aviator sunglasses somewhere between the sports complex and the parking lot. Gold frame, green lenses. They were in a brown leather case.",
            "category": "👓 Eyewear", "location": "🏟️ Sports Complex",
            "date_occurred": (now - timedelta(days=4)).strftime("%Y-%m-%d"),
            "poster_name": "Kavya Reddy", "poster_email": "kavya.r@campus.edu",
            "poster_phone": "", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "TI-84 Scientific Calculator",
            "description": "Found a TI-84 Plus calculator left behind in Computer Lab after the data structures session. Name 'Nikhil' is written on the back in marker.",
            "category": "📱 Electronics", "location": "💻 Computer Lab",
            "date_occurred": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "poster_name": "Sneha Gupta", "poster_email": "sneha.g@campus.edu",
            "poster_phone": "+91-9876543215", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "College ID Card — Nikhil Bansal",
            "description": "Lost my college ID card. Name: Nikhil Bansal, Roll No: 2024BCS045. I think I dropped it somewhere around the admin office or canteen area.",
            "category": "💳 ID Card / Documents", "location": "🏢 Admin Office",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Nikhil Bansal", "poster_email": "nikhil.b@campus.edu",
            "poster_phone": "+91-9876543216", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "Student ID Card Found at Canteen",
            "description": "Found a student ID card on the floor of the canteen. Belongs to someone from 2024 batch, BCS stream. Left it at the canteen counter.",
            "category": "💳 ID Card / Documents", "location": "☕ Canteen",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Tanvi Shah", "poster_email": "tanvi.s@campus.edu",
            "poster_phone": "+91-9876543217", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "MacBook Charger (USB-C, 67W)",
            "description": "Left my MacBook charger plugged in at the library charging station (ground floor, near the entrance). It's a 67W USB-C Apple charger with a braided cable.",
            "category": "🔌 Charger / Cable", "location": "📚 Library",
            "date_occurred": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
            "poster_name": "Rohan Iyer", "poster_email": "rohan.i@campus.edu",
            "poster_phone": "", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "North Face Backpack (Grey)",
            "description": "Found a grey North Face backpack left on a bench near the campus garden. Contains some notebooks and a pencil case. No name tag visible.",
            "category": "🎒 Bag / Backpack", "location": "🌳 Campus Garden / Quad",
            "date_occurred": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "poster_name": "Aisha Khan", "poster_email": "aisha.k@campus.edu",
            "poster_phone": "+91-9876543218", "status": "open",
        },
        {
            "id": gen_id(), "type": "lost",
            "title": "Silver Casio Watch",
            "description": "Lost my silver Casio digital watch in the sports complex locker room. It has a silver metal band and blue digital display. Sentimental value — it was a gift.",
            "category": "⌚ Watch / Jewelry", "location": "🏟️ Sports Complex",
            "date_occurred": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "poster_name": "Dev Kapoor", "poster_email": "dev.k@campus.edu",
            "poster_phone": "+91-9876543219", "status": "open",
        },
        {
            "id": gen_id(), "type": "found",
            "title": "Prescription Glasses (Black Frame)",
            "description": "Found black rectangular prescription glasses on a seat in the auditorium after the cultural fest rehearsal. They're in a grey hard case.",
            "category": "👓 Eyewear", "location": "🎭 Auditorium",
            "date_occurred": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "poster_name": "Riya Verma", "poster_email": "riya.v@campus.edu",
            "poster_phone": "+91-9876543220", "status": "open",
        },
    ]
    for item in seed_items:
        conn.execute(
            """INSERT INTO items (id, type, title, description, category, location,
               date_occurred, date_posted, photo, photo_hash, poster_name, poster_email,
               poster_phone, status, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item["id"], item["type"], item["title"], item["description"],
                item["category"], item["location"], item["date_occurred"],
                (now - timedelta(hours=hash(item["id"]) % 48)).isoformat(),
                None, "", item["poster_name"], item["poster_email"],
                item.get("poster_phone", ""), item["status"], "[]"
            )
        )
    conn.commit()
    conn.close()

seed_data()


# ─── Session State Init ────────────────────────────────────────────────────

if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "active_item_detail" not in st.session_state:
    st.session_state.active_item_detail = None
if "show_claim_form" not in st.session_state:
    st.session_state.show_claim_form = None


# ─── Inject CSS ─────────────────────────────────────────────────────────────
inject_css()


# ─── Onboarding / Quick Identity ────────────────────────────────────────────

def render_onboarding():
    st.markdown("""
    <div class="hero-section">
        <div class="hero-title">🔍 FindIt</div>
        <div class="hero-sub">Your campus lost & found — reimagined</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="background: white; border-radius: 16px; padding: 2rem; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center;">
            <h3 style="color: #2D3436; margin-bottom: 0.5rem;">Welcome to FindIt 👋</h3>
            <p style="color: #636E72; font-size: 0.95rem; margin-bottom: 1.5rem;">
                Enter your name and campus email to get started.<br>
                <span style="font-size: 0.8rem; color: #B2BEC3;">No password needed — just so people can reach you about your items.</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("onboarding_form", clear_on_submit=False):
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

        st.markdown("""
        <div style="text-align: center; margin-top: 1.5rem;">
            <p style="color: #B2BEC3; font-size: 0.8rem;">
                🔒 We only use your email for item notifications. No spam, ever.
            </p>
        </div>
        """, unsafe_allow_html=True)


# ─── Render Nav Bar ─────────────────────────────────────────────────────────

def render_nav():
    conn = get_db()
    total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    lost_count = conn.execute("SELECT COUNT(*) FROM items WHERE type = 'lost' AND status = 'open'").fetchone()[0]
    found_count = conn.execute("SELECT COUNT(*) FROM items WHERE type = 'found' AND status = 'open'").fetchone()[0]
    returned_count = conn.execute("SELECT COUNT(*) FROM items WHERE status = 'returned'").fetchone()[0]
    conn.close()

    st.markdown(f"""
    <div class="nav-bar">
        <div class="nav-brand">
            <span class="logo-icon">🔍</span>
            <div>
                <h1>FindIt</h1>
                <div class="nav-subtitle">Campus Lost & Found</div>
            </div>
        </div>
        <div class="nav-stats">
            <div class="nav-stat">
                <div class="nav-stat-number">{lost_count}</div>
                <div class="nav-stat-label">Lost</div>
            </div>
            <div class="nav-stat">
                <div class="nav-stat-number">{found_count}</div>
                <div class="nav-stat-label">Found</div>
            </div>
            <div class="nav-stat">
                <div class="nav-stat-number">{returned_count}</div>
                <div class="nav-stat-label">Reunited ✨</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Render Item Card (HTML) ───────────────────────────────────────────────

def render_item_card_html(item, show_actions=True):
    badge_class = "badge-lost" if item['type'] == 'lost' else "badge-found"
    badge_text = "LOST" if item['type'] == 'lost' else "FOUND"
    initials = get_initials(item['poster_name'])
    time_text = time_ago(item['date_posted'])
    status_class = f"status-{item['status']}"

    photo_html = ""
    if item.get('photo'):
        b64 = image_to_base64(item['photo']) if isinstance(item['photo'], bytes) else item['photo']
        photo_html = f'<img src="data:image/jpeg;base64,{b64}" class="card-image" />'
    else:
        # Placeholder with category emoji
        emoji = item['category'].split()[0] if item['category'] else "📦"
        photo_html = f"""
        <div style="width: 100%; aspect-ratio: 4/3; background: linear-gradient(135deg, #F5F5F5, #EBEBEB);
                    display: flex; align-items: center; justify-content: center; font-size: 4rem; opacity: 0.4;">
            {emoji}
        </div>
        """

    return f"""
    <div class="item-card animate-in">
        <div class="card-header">
            <div class="card-poster">
                <div class="card-avatar">{initials}</div>
                <div>
                    <div class="card-poster-name">{item['poster_name']}</div>
                    <div class="card-poster-time">{time_text}</div>
                </div>
            </div>
            <span class="card-type-badge {badge_class}">{badge_text}</span>
        </div>
        {photo_html}
        <div class="card-body">
            <div class="card-title">{item['title']}</div>
            <div class="card-desc">{item['description'][:150]}{'...' if len(item['description']) > 150 else ''}</div>
            <div class="card-meta">
                <span class="meta-chip">📍 {item['location']}</span>
                <span class="meta-chip">📅 {item['date_occurred']}</span>
                <span class="meta-chip">{item['category']}</span>
                <span class="meta-chip {status_class}">● {item['status'].title()}</span>
            </div>
        </div>
    </div>
    """


# ─── Feed View ──────────────────────────────────────────────────────────────

def render_feed():
    conn = get_db()

    # Filters
    st.markdown('<div class="section-header"><h2>📰 Live Feed</h2></div>', unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1, 1])
    with filter_col1:
        type_filter = st.selectbox("Type", ["All", "Lost", "Found"], key="feed_type")
    with filter_col2:
        cat_filter = st.selectbox("Category", ["All"] + CATEGORIES, key="feed_cat")
    with filter_col3:
        loc_filter = st.selectbox("Location", ["All"] + LOCATIONS, key="feed_loc")
    with filter_col4:
        search_q = st.text_input("🔍 Search", placeholder="Search items...", key="feed_search")

    query = "SELECT * FROM items WHERE 1=1"
    params = []
    if type_filter != "All":
        query += " AND type = ?"
        params.append(type_filter.lower())
    if cat_filter != "All":
        query += " AND category = ?"
        params.append(cat_filter)
    if loc_filter != "All":
        query += " AND location = ?"
        params.append(loc_filter)
    if search_q.strip():
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])
    query += " ORDER BY date_posted DESC"

    items = conn.execute(query, params).fetchall()
    conn.close()

    if not items:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-text">No items found matching your filters.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Grid layout
    cols = st.columns(2)
    for idx, item in enumerate(items):
        item_dict = dict(item)
        with cols[idx % 2]:
            st.markdown(render_item_card_html(item_dict), unsafe_allow_html=True)
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🔎 Details", key=f"detail_{item_dict['id']}", use_container_width=True):
                    st.session_state.active_item_detail = item_dict['id']
                    st.rerun()
            with btn_col2:
                if item_dict['status'] == 'open' and item_dict['poster_email'] != st.session_state.user_email:
                    claim_label = "🙋 This is Mine!" if item_dict['type'] == 'found' else "✋ I Found This!"
                    if st.button(claim_label, key=f"claim_{item_dict['id']}", use_container_width=True, type="primary"):
                        st.session_state.show_claim_form = item_dict['id']
                        st.session_state.active_item_detail = item_dict['id']
                        st.rerun()


# ─── Post Item View ────────────────────────────────────────────────────────

def render_post():
    st.markdown('<div class="section-header"><h2>📝 Post an Item</h2></div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="background: linear-gradient(135deg, #DFE6E9 0%, #F5F5F5 100%); border-radius: 12px; padding: 16px 20px; margin-bottom: 1.5rem;">
        <p style="margin: 0; color: #636E72; font-size: 0.9rem;">
            <strong>💡 Tip:</strong> Add as much detail as possible — color, brand, distinguishing marks.
            A photo boosts match chances by <strong>3×</strong>!
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("post_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            item_type = st.radio(
                "What are you posting?",
                ["🔴 I Lost Something", "🟢 I Found Something"],
                horizontal=True,
                key="post_type"
            )
            resolved_type = "lost" if "Lost" in item_type else "found"

            title = st.text_input(
                "Item Title *",
                placeholder="e.g., Black Leather Wallet with Initials 'RS'"
            )
            category = st.selectbox("Category *", CATEGORIES, key="post_cat")
            location = st.selectbox("Location *", LOCATIONS, key="post_loc")

        with col2:
            date_occurred = st.date_input(
                "When did you lose/find it? *",
                value=datetime.now().date(),
                max_value=datetime.now().date()
            )
            description = st.text_area(
                "Description *",
                placeholder="Describe the item in detail — color, brand, size, any identifying marks, exactly where you think it might be...",
                height=130
            )
            photo = st.file_uploader(
                "📷 Upload a Photo (highly recommended)",
                type=["jpg", "jpeg", "png", "webp"],
                key="post_photo"
            )

        phone = st.text_input(
            "Phone (optional — for WhatsApp notifications)",
            placeholder="+91-9876543210"
        )

        submitted = st.form_submit_button("🚀 Post Item", use_container_width=True, type="primary")

        if submitted:
            if not title.strip():
                st.error("Please enter an item title.")
            elif not description.strip():
                st.error("Please add a description so people can identify the item.")
            else:
                photo_bytes = None
                photo_hash = ""
                if photo is not None:
                    photo_bytes = photo.read()
                    photo_hash = compute_image_hash(photo_bytes)

                item_id = gen_id()
                conn = get_db()
                conn.execute(
                    """INSERT INTO items (id, type, title, description, category, location,
                       date_occurred, date_posted, photo, photo_hash, poster_name, poster_email,
                       poster_phone, status, tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', '[]')""",
                    (
                        item_id, resolved_type, title.strip(), description.strip(),
                        category, location, date_occurred.isoformat(),
                        datetime.now().isoformat(), photo_bytes, photo_hash,
                        st.session_state.user_name, st.session_state.user_email,
                        phone.strip()
                    )
                )
                conn.commit()
                conn.close()

                # Auto-match and notify
                matches = find_matches(item_id, top_n=3)
                for match_item, score in matches:
                    if score >= 0.25:
                        pct = int(score * 100)
                        # Notify both parties
                        create_notification(
                            st.session_state.user_email,
                            f"🎯 Potential Match Found ({pct}%)",
                            f"Your {resolved_type} item '{title}' may match '{match_item['title']}' posted by {match_item['poster_name']}. Check your matches tab!",
                            "match", item_id
                        )
                        create_notification(
                            match_item['poster_email'],
                            f"🎯 Potential Match Found ({pct}%)",
                            f"A new {resolved_type} item '{title}' posted by {st.session_state.user_name} may match your item '{match_item['title']}'. Check your matches tab!",
                            "match", match_item['id']
                        )
                        # Attempt email
                        send_email_notification(
                            match_item['poster_email'],
                            f"FindIt: Potential match for '{match_item['title']}'",
                            f"Hi {match_item['poster_name']},\n\nA new item '{title}' was just posted that matches your listing '{match_item['title']}' with {pct}% confidence.\n\nLog in to FindIt to check it out!"
                        )

                st.success("🎉 Item posted successfully!")
                if matches and matches[0][1] >= 0.25:
                    st.info(f"✨ We found {len([m for m in matches if m[1] >= 0.25])} potential match(es)! Check the Matches tab.")
                st.balloons()


# ─── Smart Matches View ────────────────────────────────────────────────────

def render_matches():
    st.markdown('<div class="section-header"><h2>🎯 Smart Matches</h2></div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 100%); border-radius: 12px; padding: 16px 20px; margin-bottom: 1.5rem; color: white;">
        <p style="margin: 0; font-size: 0.9rem;">
            <strong>How matching works:</strong> Our engine compares category, title, description, location, date proximity,
            and image similarity (perceptual hashing) to find probable matches between lost and found items.
        </p>
    </div>
    """, unsafe_allow_html=True)

    conn = get_db()
    my_items = conn.execute(
        "SELECT * FROM items WHERE poster_email = ? AND status = 'open' ORDER BY date_posted DESC",
        (st.session_state.user_email,)
    ).fetchall()
    all_open = conn.execute(
        "SELECT * FROM items WHERE status = 'open' ORDER BY date_posted DESC"
    ).fetchall()
    conn.close()

    # Section 1: Matches for my items
    if my_items:
        st.markdown("#### 🔗 Matches for Your Items")
        for item in my_items:
            item_dict = dict(item)
            matches = find_matches(item_dict['id'], top_n=5)
            type_emoji = "🔴" if item_dict['type'] == 'lost' else "🟢"

            with st.expander(f"{type_emoji} {item_dict['title']} — {len(matches)} potential match(es)", expanded=False):
                if not matches:
                    st.markdown("No matches found yet. Check back later as new items are posted!")
                else:
                    for match_item, score in matches:
                        pct = int(score * 100)
                        score_class = "score-high" if pct >= 60 else "score-med" if pct >= 35 else "score-low"
                        st.markdown(f"""
                        <div style="background: white; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px; border: 1px solid #eee; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <strong style="font-size: 0.95rem;">{match_item['title']}</strong>
                                <span style="font-weight: 700; font-size: 0.9rem; color: {'#00B894' if pct >= 60 else '#FDCB6E' if pct >= 35 else '#E17055'};">{pct}% match</span>
                            </div>
                            <div class="match-score-container">
                                <div class="match-score-fill {score_class}" style="width: {pct}%;"></div>
                            </div>
                            <p style="font-size: 0.85rem; color: #636E72; margin: 8px 0 4px 0;">{match_item['description'][:120]}...</p>
                            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                <span class="meta-chip">📍 {match_item['location']}</span>
                                <span class="meta-chip">📅 {match_item['date_occurred']}</span>
                                <span class="meta-chip">👤 {match_item['poster_name']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("View Details", key=f"match_detail_{item_dict['id']}_{match_item['id']}", use_container_width=True):
                                st.session_state.active_item_detail = match_item['id']
                                st.rerun()
                        with btn_col2:
                            claim_label = "🙋 This is Mine!" if match_item['type'] == 'found' else "✋ I Found This!"
                            if st.button(claim_label, key=f"match_claim_{item_dict['id']}_{match_item['id']}", use_container_width=True, type="primary"):
                                st.session_state.show_claim_form = match_item['id']
                                st.session_state.active_item_detail = match_item['id']
                                st.rerun()
    else:
        st.info("Post an item to see smart matches here!")

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # Section 2: Global match explorer
    st.markdown("#### 🌐 Match Explorer")
    st.markdown("Select any open item to see its best matches:")

    if all_open:
        item_options = {f"{dict(i)['type'].upper()}: {dict(i)['title']}": dict(i)['id'] for i in all_open}
        selected = st.selectbox("Pick an item", list(item_options.keys()), key="match_explorer_select")
        if selected:
            sel_id = item_options[selected]
            matches = find_matches(sel_id, top_n=5)
            if matches:
                for match_item, score in matches:
                    pct = int(score * 100)
                    score_class = "score-high" if pct >= 60 else "score-med" if pct >= 35 else "score-low"
                    st.markdown(f"""
                    <div style="background: white; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px; border: 1px solid #eee;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong>{match_item['title']}</strong>
                            <span style="font-weight: 700; color: {'#00B894' if pct >= 60 else '#FDCB6E' if pct >= 35 else '#E17055'};">{pct}%</span>
                        </div>
                        <div class="match-score-container"><div class="match-score-fill {score_class}" style="width: {pct}%;"></div></div>
                        <p style="font-size: 0.85rem; color: #636E72; margin: 6px 0;">{match_item['description'][:100]}...</p>
                        <span class="meta-chip">📍 {match_item['location']}</span>
                        <span class="meta-chip">👤 {match_item['poster_name']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No matches found for this item.")


# ─── Item Detail & Claim Workflow ───────────────────────────────────────────

def render_item_detail():
    item_id = st.session_state.active_item_detail
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        st.error("Item not found.")
        conn.close()
        return

    item_dict = dict(item)
    claims = conn.execute(
        "SELECT * FROM claims WHERE item_id = ? ORDER BY date_claimed DESC",
        (item_id,)
    ).fetchall()
    conn.close()
    claims = [dict(c) for c in claims]

    # Back button
    if st.button("← Back to Feed"):
        st.session_state.active_item_detail = None
        st.session_state.show_claim_form = None
        st.rerun()

    st.markdown(render_item_card_html(item_dict, show_actions=False), unsafe_allow_html=True)

    # Full description
    st.markdown(f"""
    <div style="background: white; border-radius: 12px; padding: 20px; margin: 1rem 0; border: 1px solid #eee;">
        <h4 style="margin-bottom: 8px;">📋 Full Description</h4>
        <p style="color: #636E72; line-height: 1.6;">{item_dict['description']}</p>
        <div style="margin-top: 12px; display: flex; gap: 12px; flex-wrap: wrap;">
            <span class="meta-chip">📍 {item_dict['location']}</span>
            <span class="meta-chip">📅 {item_dict['date_occurred']}</span>
            <span class="meta-chip">{item_dict['category']}</span>
            <span class="meta-chip">📧 {item_dict['poster_email']}</span>
            {'<span class="meta-chip">📱 ' + item_dict['poster_phone'] + '</span>' if item_dict.get('poster_phone') else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Matches for this item
    matches = find_matches(item_id, top_n=3)
    if matches:
        st.markdown("#### 🎯 Potential Matches")
        for match_item, score in matches:
            pct = int(score * 100)
            st.markdown(f"""
            <div style="background: #F9F9FF; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; border-left: 3px solid #6C5CE7;">
                <strong>{match_item['title']}</strong> — <span style="color: #6C5CE7; font-weight: 600;">{pct}% match</span>
                <br><span style="font-size: 0.85rem; color: #636E72;">by {match_item['poster_name']} · {match_item['location']}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # ── Claim Section ──
    is_poster = item_dict['poster_email'] == st.session_state.user_email
    already_claimed = any(c['claimer_email'] == st.session_state.user_email for c in claims)

    if item_dict['status'] == 'open' and not is_poster and not already_claimed:
        claim_label = "🙋 Claim: This is My Item!" if item_dict['type'] == 'found' else "✋ Claim: I Found This Item!"
        if st.button(claim_label, type="primary", use_container_width=True, key="detail_claim_btn"):
            st.session_state.show_claim_form = item_id

    if st.session_state.show_claim_form == item_id:
        st.markdown("""
        <div style="background: #F0EDFF; border-radius: 12px; padding: 16px 20px; margin: 1rem 0;">
            <h4 style="color: #6C5CE7; margin-bottom: 4px;">📋 Submit Your Claim</h4>
            <p style="font-size: 0.85rem; color: #636E72;">Describe why you believe this is your item (or that you found it).
            Include identifying details the poster didn't mention to prove ownership.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("claim_form", clear_on_submit=True):
            claim_msg = st.text_area(
                "Your Claim Message *",
                placeholder="Example: This is my wallet — it's brown with initials 'RS' embossed, and it also has a Starbucks loyalty card inside...",
                height=100
            )
            proof_desc = st.text_area(
                "Proof of Ownership (describe identifying details others wouldn't know)",
                placeholder="E.g., 'There's a torn receipt from Chai Point inside the front pocket dated March 10'",
                height=80
            )
            claimer_phone = st.text_input("Your Phone (optional)", placeholder="+91-9876543210")
            claim_submitted = st.form_submit_button("Submit Claim", type="primary", use_container_width=True)

            if claim_submitted:
                if not claim_msg.strip():
                    st.error("Please describe why this item is yours.")
                else:
                    claim_id = gen_id()
                    conn = get_db()
                    conn.execute(
                        """INSERT INTO claims (id, item_id, claimer_name, claimer_email, claimer_phone,
                           message, proof_description, status, date_claimed)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                        (
                            claim_id, item_id, st.session_state.user_name,
                            st.session_state.user_email, claimer_phone.strip(),
                            claim_msg.strip(), proof_desc.strip(),
                            datetime.now().isoformat()
                        )
                    )
                    conn.commit()
                    conn.close()

                    # Notify the poster
                    create_notification(
                        item_dict['poster_email'],
                        f"🙋 New Claim on '{item_dict['title']}'",
                        f"{st.session_state.user_name} has claimed your item '{item_dict['title']}'. Review their claim in 'My Items' → Claims.",
                        "claim", item_id
                    )
                    send_email_notification(
                        item_dict['poster_email'],
                        f"FindIt: Someone claimed '{item_dict['title']}'",
                        f"Hi {item_dict['poster_name']},\n\n{st.session_state.user_name} just submitted a claim on your item '{item_dict['title']}'.\n\nLog in to FindIt to review the claim and accept or reject it."
                    )

                    st.success("✅ Claim submitted! The poster will be notified and can accept or reject your claim.")
                    st.session_state.show_claim_form = None
                    st.rerun()

    # ── Poster's Claim Management ──
    if is_poster and claims:
        st.markdown("#### 📬 Claims on Your Item")
        st.markdown(f"**{len(claims)} claim(s)** received. Review each one and accept or reject.")

        for claim in claims:
            status_color = {"pending": "#6C5CE7", "accepted": "#00B894", "rejected": "#E17055"}
            status_label = claim['status'].upper()
            card_class = claim['status']

            st.markdown(f"""
            <div class="claim-card {card_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div>
                        <strong>{claim['claimer_name']}</strong>
                        <span style="color: #B2BEC3; font-size: 0.8rem;"> · {claim['claimer_email']}</span>
                    </div>
                    <span style="background: {status_color.get(claim['status'], '#B2BEC3')}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.7rem; font-weight: 600;">{status_label}</span>
                </div>
                <p style="color: #636E72; font-size: 0.9rem; margin: 4px 0;">{claim['message']}</p>
                {'<p style="color: #6C5CE7; font-size: 0.85rem; margin: 4px 0;"><strong>Proof:</strong> ' + claim['proof_description'] + '</p>' if claim.get('proof_description') else ''}
                {'<p style="font-size: 0.8rem; color: #B2BEC3;">📱 ' + claim['claimer_phone'] + '</p>' if claim.get('claimer_phone') else ''}
                <p style="font-size: 0.75rem; color: #B2BEC3;">Claimed {time_ago(claim['date_claimed'])}</p>
            </div>
            """, unsafe_allow_html=True)

            if claim['status'] == 'pending':
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Accept", key=f"accept_{claim['id']}", use_container_width=True, type="primary"):
                        conn = get_db()
                        # Accept this claim
                        conn.execute("UPDATE claims SET status = 'accepted' WHERE id = ?", (claim['id'],))
                        # Reject all other pending claims
                        conn.execute(
                            "UPDATE claims SET status = 'rejected' WHERE item_id = ? AND id != ? AND status = 'pending'",
                            (item_id, claim['id'])
                        )
                        # Mark item as matched/returned
                        conn.execute(
                            "UPDATE items SET status = 'returned', matched_with = ? WHERE id = ?",
                            (claim['claimer_email'], item_id)
                        )
                        conn.commit()
                        conn.close()

                        # Notify the claimer
                        create_notification(
                            claim['claimer_email'],
                            f"🎉 Your Claim Was Accepted!",
                            f"{item_dict['poster_name']} accepted your claim on '{item_dict['title']}'! Reach out to them at {item_dict['poster_email']} to arrange the handover.",
                            "claim_accepted", item_id
                        )
                        send_email_notification(
                            claim['claimer_email'],
                            f"FindIt: Your claim on '{item_dict['title']}' was accepted!",
                            f"Great news! {item_dict['poster_name']} accepted your claim. Contact them at {item_dict['poster_email']} to get your item back!"
                        )
                        # Notify rejected claimers
                        conn2 = get_db()
                        rejected = conn2.execute(
                            "SELECT * FROM claims WHERE item_id = ? AND status = 'rejected'",
                            (item_id,)
                        ).fetchall()
                        for rej in rejected:
                            rej = dict(rej)
                            create_notification(
                                rej['claimer_email'],
                                f"Claim Update: '{item_dict['title']}'",
                                f"Unfortunately, your claim on '{item_dict['title']}' was not accepted. The item has been returned to another claimant.",
                                "claim_rejected", item_id
                            )
                        conn2.close()

                        st.success("Claim accepted! The claimer has been notified.")
                        st.rerun()

                with col_b:
                    if st.button("❌ Reject", key=f"reject_{claim['id']}", use_container_width=True):
                        conn = get_db()
                        conn.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim['id'],))
                        conn.commit()
                        conn.close()

                        create_notification(
                            claim['claimer_email'],
                            f"Claim Not Accepted: '{item_dict['title']}'",
                            f"Your claim on '{item_dict['title']}' was not accepted by the poster. This may be because the details didn't match sufficiently.",
                            "claim_rejected", item_id
                        )
                        st.warning("Claim rejected.")
                        st.rerun()

    elif is_poster and not claims:
        st.info("No claims yet. We'll notify you when someone claims this item.")


# ─── My Items View ──────────────────────────────────────────────────────────

def render_my_items():
    st.markdown('<div class="section-header"><h2>📦 My Items</h2></div>', unsafe_allow_html=True)

    conn = get_db()
    my_items = conn.execute(
        "SELECT * FROM items WHERE poster_email = ? ORDER BY date_posted DESC",
        (st.session_state.user_email,)
    ).fetchall()

    my_claims = conn.execute(
        """SELECT c.*, i.title as item_title, i.type as item_type, i.poster_name as item_poster
           FROM claims c JOIN items i ON c.item_id = i.id
           WHERE c.claimer_email = ? ORDER BY c.date_claimed DESC""",
        (st.session_state.user_email,)
    ).fetchall()
    conn.close()

    tab1, tab2 = st.tabs(["📮 My Posts", "🙋 My Claims"])

    with tab1:
        if not my_items:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📮</div>
                <div class="empty-state-text">You haven't posted any items yet.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for item in my_items:
                item_dict = dict(item)
                conn2 = get_db()
                claim_count = conn2.execute(
                    "SELECT COUNT(*) FROM claims WHERE item_id = ?", (item_dict['id'],)
                ).fetchone()[0]
                pending_count = conn2.execute(
                    "SELECT COUNT(*) FROM claims WHERE item_id = ? AND status = 'pending'",
                    (item_dict['id'],)
                ).fetchone()[0]
                conn2.close()

                st.markdown(render_item_card_html(item_dict), unsafe_allow_html=True)

                info_col, action_col = st.columns([2, 1])
                with info_col:
                    if claim_count > 0:
                        st.markdown(f"📬 **{claim_count} claim(s)** — {pending_count} pending review")
                with action_col:
                    if st.button("Manage →", key=f"manage_{item_dict['id']}", use_container_width=True, type="primary"):
                        st.session_state.active_item_detail = item_dict['id']
                        st.rerun()

                st.markdown("---")

    with tab2:
        if not my_claims:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">🙋</div>
                <div class="empty-state-text">You haven't claimed any items yet.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for claim in my_claims:
                claim_dict = dict(claim)
                status_emoji = {"pending": "⏳", "accepted": "✅", "rejected": "❌"}
                emoji = status_emoji.get(claim_dict['status'], "")
                st.markdown(f"""
                <div class="claim-card {claim_dict['status']}">
                    <strong>{claim_dict['item_title']}</strong>
                    <span style="font-size: 0.85rem; color: #B2BEC3;"> · {claim_dict['item_type'].title()} item by {claim_dict['item_poster']}</span>
                    <br><span style="font-size: 0.9rem;">{emoji} {claim_dict['status'].title()}</span>
                    <p style="color: #636E72; font-size: 0.85rem; margin-top: 6px;">{claim_dict['message'][:100]}...</p>
                </div>
                """, unsafe_allow_html=True)


# ─── Notifications View ────────────────────────────────────────────────────

def render_notifications():
    unread = count_unread(st.session_state.user_email)
    notif_badge = f'<span class="notif-badge">{unread}</span>' if unread > 0 else ""
    st.markdown(f'<div class="section-header"><h2>🔔 Notifications {notif_badge}</h2></div>', unsafe_allow_html=True)

    notifs = get_notifications(st.session_state.user_email)

    if st.button("Mark All as Read", key="mark_read"):
        mark_notifications_read(st.session_state.user_email)
        st.rerun()

    if not notifs:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">🔔</div>
            <div class="empty-state-text">No notifications yet. We'll alert you on matches and claims!</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for notif in notifs:
            bg = "#F0EDFF" if not notif['read'] else "white"
            border = "2px solid #6C5CE7" if not notif['read'] else "1px solid #eee"
            st.markdown(f"""
            <div style="background: {bg}; border: {border}; border-radius: 12px; padding: 14px 18px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="font-size: 0.95rem;">{notif['subject']}</strong>
                    <span style="font-size: 0.75rem; color: #B2BEC3;">{time_ago(notif['date_created'])}</span>
                </div>
                <p style="color: #636E72; font-size: 0.88rem; margin: 6px 0 0 0;">{notif['body']}</p>
            </div>
            """, unsafe_allow_html=True)


# ─── Main App Router ───────────────────────────────────────────────────────

def main():
    if not st.session_state.logged_in:
        render_onboarding()
        return

    render_nav()

    # If viewing an item detail, show that
    if st.session_state.active_item_detail:
        render_item_detail()
        return

    # Sidebar user info
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align: center; padding: 1rem 0;">
            <div style="width: 60px; height: 60px; border-radius: 50%;
                        background: linear-gradient(135deg, #6C5CE7, #00CEC9);
                        display: flex; align-items: center; justify-content: center;
                        color: white; font-weight: 700; font-size: 1.2rem;
                        margin: 0 auto 8px auto;">
                {get_initials(st.session_state.user_name)}
            </div>
            <strong>{st.session_state.user_name}</strong><br>
            <span style="font-size: 0.8rem; color: #B2BEC3;">{st.session_state.user_email}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("🚪 Switch User", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.user_name = ""
            st.rerun()

        st.markdown("---")
        st.markdown("""
        <div style="font-size: 0.75rem; color: #B2BEC3; text-align: center;">
            <strong>FindIt v1.0</strong><br>
            Campus Lost & Found Portal<br>
            Built with ❤️ using Streamlit
        </div>
        """, unsafe_allow_html=True)

    # Main tabs
    unread = count_unread(st.session_state.user_email)
    notif_label = f"🔔 Alerts ({unread})" if unread > 0 else "🔔 Alerts"

    tab_feed, tab_post, tab_matches, tab_myitems, tab_notifs = st.tabs([
        "📰 Feed", "📝 Post", "🎯 Matches", "📦 My Items", notif_label
    ])

    with tab_feed:
        render_feed()
    with tab_post:
        render_post()
    with tab_matches:
        render_matches()
    with tab_myitems:
        render_my_items()
    with tab_notifs:
        render_notifications()


if __name__ == "__main__":
    main()
