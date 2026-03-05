# 🛡️ Secure Crime Reporting System

---

## 📐 System Architecture

```
Two Portals, One Login Page
├── CITIZEN PORTAL  (login with National ID)
│   ├── Dashboard          — report stats + quick actions
│   ├── Report (Named)     — file with identity linked
│   ├── Report Anonymous   — fully anonymous, no ID stored
│   ├── My Reports         — track all your submissions
│   ├── SOS Emergency      — instant officer alert + contacts
│   └── Safety Tips        — categorized safety guidance
│
└── OFFICER PORTAL  (login with Officer ID + password)
    ├── Dashboard          — live stats, donut chart, recent cases, trends
    ├── All Cases          — filter/search/paginate, case detail modal
    └── Analytics          — 12-month trend, crime types, hourly heatmap, county map, officer performance
```

---

## ⚡ SETUP — 3 Steps

---

### STEP 1 — Install PostgreSQL + Create Database via pgAdmin (GUI)

#### 1a. Download & Install PostgreSQL
- Go to: **https://www.postgresql.org/download**
- Download the installer for your OS (Windows/Mac/Linux)
- Run the installer:
  - Choose all default options
  - When asked for a **password**, set it to `postgres` (or remember what you set — you'll need it)
  - Keep the default port **5432**
  - **pgAdmin 4** is included and will install automatically

#### 1b. Open pgAdmin and Connect
1. Open **pgAdmin 4** from your Start Menu (Windows) or Applications (Mac)
2. In the left panel, expand **Servers**
3. Click **PostgreSQL** → enter your password when prompted
4. You are now connected

#### 1c. Create the Database
1. Right-click **Databases** (in the left panel)
2. Click **Create → Database**
3. In the "Database" field, type: **`crime_db`**
4. Click **Save**
5. You'll see `crime_db` appear in the left panel

#### 1d. Run the Schema (create all tables)
1. Click on **`crime_db`** in the left panel to select it *(important!)*
2. Click the **Query Tool** button in the top toolbar (looks like a lightning bolt ⚡)
3. In the Query Tool, click the **folder icon** (Open File) 📂
4. Navigate to `crime-reporting-system/backend/` → select `schema.sql` → click Open
5. Press **F5** or click the **▶ Execute** button
6. You should see: `Query returned successfully`

---

### STEP 2 — Python Backend

Open your **Terminal** (Mac/Linux) or **Command Prompt / PowerShell** (Windows):

```bash
# 1. Navigate to the backend folder
cd crime-reporting-system/backend

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it:
#    Windows:
venv\Scripts\activate
#    Mac / Linux:
source venv/bin/activate

# 4. Install all packages
pip install -r requirements.txt

# 5. Seed the database (creates demo users & 40 sample reports)
python seed.py

# 6. Start the server
python app.py
```

✅ You should see:
```
 * Running on http://0.0.0.0:5000
```

> **Changed your postgres password?** Edit `backend/.env` and update `DB_PASS=yourpassword`

---

### STEP 3 — Open the Frontend

**Option A — Direct open (simplest):**
Double-click `frontend/index.html` to open in your browser.

**Option B — If you get CORS errors, run a local server:**
```bash
cd crime-reporting-system/frontend
python -m http.server 8080
```
Then visit: **http://localhost:8080**

---

## 🔐 Login Credentials

### Citizens (enter National ID on login page)
| Name | National ID |
|------|-------------|
| John Kariuki | `30012345` |
| Mary Wanjiku | `28564321` |
| Peter Odhiambo | `32109876` |
| Fatuma Ali | `25678432` |
| George Njoroge | `29001122` |

> **Or enter any ID number** to auto-register as a new citizen

### Officers (Officer ID + password)
**Password for all officers: `Officer123!`**

| Name | Officer ID |
|------|-----------|
| Inspector James Mwangi | `OFC-001` |
| Sgt. Grace Otieno | `OFC-002` |
| Cpl. Brian Kamau | `OFC-003` |
| Const. Aisha Hassan | `OFC-004` |
| Chief Insp. David Omondi | `OFC-005` |

---

## 🗂️ Full Feature Breakdown

### Login Page
- **Portal toggle slider** — switches between Citizen and Officer login
- **Citizen login** — enter National ID, auto-registers if first time
- **Officer login** — Officer ID + password with JWT auth
- **Anonymous button** — goes directly to anonymous report page (no login)
- **Demo credentials** — click "Use" buttons to auto-fill

### Citizen — Dashboard
- 4 stat cards: Total / Pending / Under Review / Resolved
- Recent reports table with status badges
- Quick action buttons (Report / Anonymous / SOS)
- Random safety tip preview

### Citizen — Report (Named)
- Full form: Crime type, County, Sub-county, Location, Date/Time
- Suspect & witness info fields
- Success screen with reference number

### Citizen — Report Anonymous
- Same form but submissions are NOT linked to citizen ID
- Works both when logged in AND without login
- Reference number returned for tracking

### Citizen — My Reports
- Filter by status
- Card grid view with type, location, status, date
- Click any card → detail modal with officer updates & timeline

### Citizen — SOS Emergency
- Large pulsing SOS button with animation
- Optional location and message fields
- Success confirmation with timestamp
- Emergency contacts with click-to-call

### Citizen — Safety Tips
- Category filter tabs: Home Security, Street Safety, Online Safety, Vehicle Safety, Emergency Contacts
- Card grid layout with icons

### Officer — Dashboard
- 6 stat cards: Total / Pending / Under Review / Resolved / My Cases / SOS Active
- Recent reports table (clickable → case modal)
- Status donut chart with legend
- Crime type bar chart
- Monthly trend chart (last 6 months)

### Officer — All Cases
- Search bar (searches ref, type, location, description)
- Filters: Status / Priority / Crime Type / "My cases" toggle
- Sortable table with priority indicators
- Pagination
- Click row → case detail modal:
  - Update status, priority, assigned officer
  - Add investigation notes
  - Full case info (description, suspect, witness)
  - Case update timeline

### Officer — Analytics
- 4 KPI cards: Avg resolution days / Resolution rate % / Top crime type / Active officers
- 12-month report trend chart
- Crime type breakdown (% bar chart)
- 24-hour heatmap bars
- County distribution bar chart
- Officer performance table

---

## 🔌 API Reference

```
POST /api/auth/citizen/login          National ID login (auto-registers)
POST /api/auth/officer/login          Officer ID + password login
GET  /api/auth/me                     Current user info

GET  /api/citizen/dashboard           Citizen stats + recent reports
GET  /api/citizen/reports             My reports (filterable)
POST /api/citizen/reports             Submit named report
POST /api/citizen/reports/anonymous   Submit anonymous report (no auth)
GET  /api/citizen/reports/:id         Report detail + updates

POST /api/citizen/sos                 Send SOS alert

GET  /api/safety-tips                 All tips (filterable by category)

GET  /api/officer/dashboard           Officer dashboard stats
GET  /api/officer/cases               All cases (filterable, paginated)
GET  /api/officer/cases/:id           Case detail + timeline
PUT  /api/officer/cases/:id           Update case (status/priority/assign)
POST /api/officer/cases/:id/note      Add investigation note
GET  /api/officer/analytics           Full analytics data

GET  /api/officers                    List active officers
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|---------|
| "Connection refused" | Make sure `python app.py` is running in the backend folder |
| "CORS error" in browser | Run `python -m http.server 8080` in the frontend folder and visit localhost:8080 |
| "Authentication failed" for PostgreSQL | Edit `backend/.env` → set `DB_PASS=yourpassword` |
| "Module not found" | Activate venv: `venv\Scripts\activate` (Win) or `source venv/bin/activate` (Mac/Linux) |
| pgAdmin "connection error" | Open Services → find postgresql-x64-XX → Start |
| Tables don't exist | Make sure you ran schema.sql on `crime_db` (not a different DB) |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue.js 3 (CDN — no build step needed) |
| CSS Framework | Bootstrap 5 |
| Fonts | Plus Jakarta Sans + Instrument Mono |
| Backend | Python 3.9 + Flask |
| Authentication | JWT (flask-jwt-extended) |
| Database | PostgreSQL |
| DB Driver | psycopg2-binary |
