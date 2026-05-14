# 📋 DECISIONS.md — Architecture & Trade-Off Log

## 1. Stack Choice: Why Streamlit + SQLite

**Decision:** Single-file Streamlit app with SQLite persistence.

**Reasoning:**
- The brief values a *working deployed demo* over architectural complexity. Streamlit lets me ship a polished, interactive app in one Python file that deploys in under 60 seconds on Streamlit Community Cloud — completely free.
- SQLite (WAL mode) gives real persistence with zero config. No external database service to provision, no connection strings, no cold-start delays. For a campus of ~5,000 students with maybe 50 items/week, SQLite handles the load trivially.
- The alternative (React + Node + Postgres) would have taken 3-5x longer and introduced deployment complexity (CORS, separate frontend/backend hosting, DB provisioning) with no material benefit for this prototype.

**Trade-off acknowledged:** Streamlit's interactivity model (full re-render on each widget change) makes complex stateful UIs harder than React. I mitigated this with careful session_state management and custom HTML/CSS for the card-based UI.

**What I'd change with more time:** Move to Next.js + Supabase for real-time updates, proper component architecture, and websocket-based notifications.

---

## 2. Authentication: Email-Only Identity (No Password)

**Decision:** Users enter name + email to identify themselves. No password, no OAuth.

**Reasoning:**
- The Dean's mandate was *"as easy as Instagram"* — and the biggest friction point in any campus tool is the signup/login flow. A prototype that requires account creation will lose 60-70% of users before they ever post an item.
- For a lost-and-found portal, the threat model is low. The worst a bad actor can do is post fake items or claim items they don't own — both of which are mitigated by the claim-review workflow (the real owner must accept a claim).
- Email serves double duty: it's both the identity key and the notification channel.

**Trade-off acknowledged:** Anyone can impersonate another user by entering their email. In production, I'd add:
1. Email verification (magic link / OTP) — still passwordless, but verified
2. Rate limiting on posts and claims per email
3. Optional campus SSO integration (SAML/OAuth with the university's identity provider)

**Why this is still safe for the prototype:** The claim workflow requires the *poster* to review and accept claims. If someone impersonates a poster, the real poster won't see the notification. If someone makes a fake claim, the poster simply rejects it. The system is self-correcting.

---

## 3. Matching Engine: Multi-Signal Weighted Scoring

**Decision:** A composite score across 6 signals with tuned weights.

| Signal | Weight | Method |
|--------|--------|--------|
| Category match | 25% | Exact match (binary) |
| Title similarity | 20% | SequenceMatcher + Jaccard token overlap |
| Description similarity | 15% | SequenceMatcher + Jaccard token overlap |
| Location match | 15% | Exact match (full) or partial text match (half) |
| Date proximity | 10% | Linear decay over 7-day window |
| Image hash similarity | 15% | Perceptual hash (pHash) Hamming distance |

**Why this approach:**
- No single signal is reliable alone. A "black wallet" lost at the cafeteria should match a "dark leather wallet found at the food court" — but only if multiple signals agree.
- Category is the strongest signal (25%) because it's a controlled vocabulary. Two items in different categories are almost never the same item.
- Image hashing (pHash) is a lightweight stretch goal that adds real value: if someone photographs a found wallet and the owner posted a photo of their wallet, perceptual hashing can detect similarity even with different lighting, angles, and cameras.
- I kept the threshold low (10%) to surface potential matches, then let humans decide. False positives are cheap (a user ignores a bad match); false negatives are expensive (a user never finds their item).

**Trade-off acknowledged:** This is a heuristic, not ML. A production system would use:
- Sentence embeddings (e.g., all-MiniLM via HuggingFace) for semantic text matching
- CLIP embeddings for image-text cross-modal matching
- User feedback loop (accepted matches improve the model over time)

---

## 4. Claim Workflow: How Ownership is Verified

**Decision:** Multi-step claim process with proof-of-ownership and poster confirmation.

**Flow:**
1. Claimer submits a message explaining why the item is theirs
2. Claimer optionally provides "proof" — identifying details only the owner would know
3. The poster receives a notification and reviews all claims
4. The poster accepts one claim → item marked "returned", all other claims auto-rejected
5. Rejected claimers are notified

**Edge case: Two people claim the same item**
- All claims are visible to the poster with their messages and proof
- The poster is the arbiter — they can compare claims side by side
- When one is accepted, all others are atomically rejected in one database transaction
- This prevents the race condition where two claims are accepted simultaneously

**Edge case: Fake claims**
- The "proof of ownership" field encourages claimers to share non-obvious details
- The poster can ask follow-up questions (via email, since both parties have each other's email after a claim)
- In production, I'd add: claim cooldown (one claim per item per user), reputation scoring, and admin moderation queue

**Edge case: Mismatched locations**
- The matching engine gives partial credit for different locations. A wallet lost "near Main Building" might be found "at the Bus Stop" — they're different locations but physically close. The 15% weight prevents location from being a hard filter.

---

## 5. Notification System: In-App + Email

**Decision:** Dual notification system — always in-app, optionally email.

**In-app notifications:**
- Zero configuration — works out of the box
- Stored in SQLite with read/unread status
- Badge count shown on the Alerts tab
- Triggers on: match found, claim submitted, claim accepted, claim rejected

**Email notifications:**
- Requires SMTP environment variables (optional)
- HTML-formatted emails matching the FindIt brand
- Triggers on the same events as in-app
- Silently fails if SMTP is not configured (no error surfaced to user)

**Why not WhatsApp:**
- WhatsApp Business API requires a verified business account and is paid beyond free tier
- Twilio's WhatsApp sandbox requires per-user opt-in via a specific message
- For a prototype, email is the most universally accessible notification channel
- The phone field is collected and stored, ready for WhatsApp integration in v2

---

## 6. Seed Data: 14 Realistic Items

**Decision:** 14 pre-seeded items spanning 9 categories and 10 locations, with deliberate match pairs.

**Match pairs built in:**
- Black wallet (lost) ↔ Brown wallet (found) — same category, same location, slight title/desc mismatch
- AirPods (lost) ↔ AirPods case (found) — high match, same location and date
- College ID (lost) ↔ Student ID (found) — same category, nearby locations

This ensures judges see the matching engine in action immediately without needing to post items.

---

## 7. UI/UX Philosophy

**Guiding principle:** Every screen should feel like a social media feed, not an enterprise form.

**Specific choices:**
- Card-based layout inspired by Instagram posts (avatar, name, time-ago, image, description, action buttons)
- Gradient nav bar and hero section for visual energy
- Emoji-prefixed categories and locations (reduces cognitive load)
- Match scores shown as colored progress bars (green/yellow/red), not raw numbers
- Claim cards with colored left-border indicating status
- Mobile-responsive CSS with media queries at 768px breakpoint
- No tables, no raw data dumps, no "admin panel" feel

---

## 8. What I'd Do Differently With More Time

| Improvement | Why |
|-------------|-----|
| **Move to Next.js + Supabase** | Real-time updates, proper component model, faster interactions |
| **Add magic-link email auth** | Verified identity without passwords |
| **Sentence embeddings (all-MiniLM)** | Far better semantic text matching |
| **CLIP-based image matching** | Cross-modal similarity (text↔image) |
| **Admin moderation dashboard** | Flag suspicious items/claims, bulk actions |
| **Campus map integration** | Pin locations on a map, proximity-based matching |
| **Push notifications (PWA)** | Instant mobile alerts without email |
| **Item expiry** | Auto-close items after 30 days, weekly digest of unclaimed items |
| **Analytics dashboard** | Track reunification rate, avg. time-to-match, busiest locations |
| **Gamification** | "Good Samaritan" badges for people who return items frequently |
