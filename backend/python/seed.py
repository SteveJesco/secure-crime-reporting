"""
Seed script — run AFTER schema.sql has been applied in pgAdmin.
Usage:  python seed.py
"""
import psycopg2, psycopg2.extras, os, random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT",5432)),
    dbname=os.getenv("DB_NAME","crime_db"), user=os.getenv("DB_USER","postgres"),
    password=os.getenv("DB_PASS","postgres"), cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# ── Clear existing seed data ──────────────────────────────────────
for t in ["report_updates","sos_alerts","reports","citizens","officers","safety_tips"]:
    cur.execute(f"DELETE FROM {t}")
conn.commit()
print("Cleared tables")

# ── Officers ──────────────────────────────────────────────────────
OFFICER_PASSWORD = "Officer123!"
officers_data = [
    ("OFC-001","Inspector James Mwangi",  "Inspector",    "CID",              "Central Police Station", "KPS-8821"),
    ("OFC-002","Sgt. Grace Otieno",       "Sergeant",     "Traffic",          "Westlands Station",      "KPS-4432"),
    ("OFC-003","Cpl. Brian Kamau",        "Corporal",     "Cybercrime Unit",  "DCI Headquarters",       "KPS-6677"),
    ("OFC-004","Const. Aisha Hassan",     "Constable",    "Community Policing","Makadara Station",      "KPS-3319"),
    ("OFC-005","Chief Insp. David Omondi","Chief Inspector","Homicide",        "Central Police Station", "KPS-1105"),
]
officer_ids = []
for oid, name, rank, dept, station, badge in officers_data:
    cur.execute(
        "INSERT INTO officers (officer_id,name,rank,department,station,badge_number,password_hash) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (oid, name, rank, dept, station, badge, generate_password_hash(OFFICER_PASSWORD)))
    officer_ids.append(cur.fetchone()["id"])
conn.commit()
print(f"Created {len(officer_ids)} officers")

# ── Citizens ──────────────────────────────────────────────────────
citizens_data = [
    ("30012345","John Kariuki",   "+254712345678","john.kariuki@gmail.com"),
    ("28564321","Mary Wanjiku",   "+254723456789","mary.w@yahoo.com"),
    ("32109876","Peter Odhiambo", "+254734567890",""),
    ("25678432","Fatuma Ali",     "+254745678901","fatuma.ali@mail.com"),
    ("29001122","George Njoroge", "+254756789012",""),
]
citizen_ids = []
for nid, name, phone, email in citizens_data:
    cur.execute("INSERT INTO citizens (national_id,display_name,phone,email) VALUES (%s,%s,%s,%s) RETURNING id",
                (nid, name, phone, email))
    citizen_ids.append(cur.fetchone()["id"])
conn.commit()
print(f"Created {len(citizen_ids)} citizens")

# ── Reports ───────────────────────────────────────────────────────
crime_types = ["Robbery","Assault","Burglary","Cybercrime","Fraud","Drug Trafficking",
               "Vehicle Theft","Domestic Violence","Vandalism","Kidnapping",
               "Sexual Harassment","Carjacking","Pickpocketing","Other"]
counties    = ["Nairobi","Mombasa","Kisumu","Nakuru","Eldoret","Thika","Nyeri",
               "Meru","Kakamega","Machakos"]
sub_counties= ["CBD","Westlands","Kasarani","Langata","Embakasi","Starehe","Pumwani"]
statuses    = ["pending","pending","under_review","under_review","resolved","dismissed"]
priorities  = ["low","medium","medium","high","critical"]
locations   = ["Tom Mboya Street, CBD","Westlands Shopping Centre","Ngong Road",
               "River Road, Nairobi","Mombasa Road","Thika Road Mall",
               "Kenyatta Avenue","Uhuru Park Area","Industrial Area","Eastleigh Estate"]

ref_counter = 10000001
report_ids  = []
for i in range(40):
    ref_counter += 1
    ref  = f"REF-{ref_counter}"
    days = random.randint(0, 120)
    dt   = datetime.now() - timedelta(days=days, hours=random.randint(0,23))
    stat = random.choice(statuses)
    cid  = random.choice(citizen_ids) if random.random() > 0.3 else None
    anon = cid is None
    ct   = random.choice(crime_types)
    prio = random.choice(priorities)
    county = random.choice(counties)
    loc  = random.choice(locations)

    if stat == "under_review":
        asgn = random.choice(officer_ids)
    elif stat == "resolved":
        asgn = random.choice(officer_ids)
    else:
        asgn = None

    cur.execute("""
        INSERT INTO reports
          (reference_number,citizen_id,is_anonymous,crime_type,description,location,
           county,sub_county,incident_date,incident_time,suspect_info,witness_info,
           status,priority,assigned_officer_id,officer_notes,created_at,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (ref, cid, anon, ct,
          f"Incident report for {ct.lower()} at {loc}. Witness stated that the incident occurred around the stated time and location. Request immediate investigation.",
          loc, county, random.choice(sub_counties),
          dt.date(), f"{random.randint(6,22):02d}:{random.choice(['00','15','30','45'])}",
          "Unknown suspect. Medium build." if random.random()>0.5 else "",
          "One witness present." if random.random()>0.6 else "",
          stat, prio, asgn,
          "Under active investigation." if stat=="under_review" else ("Case closed, suspect apprehended." if stat=="resolved" else ""),
          dt, dt))
    rid = cur.fetchone()["id"]
    report_ids.append(rid)

    # Add update log for non-pending
    if stat in ("under_review","resolved","dismissed") and asgn:
        cur.execute("INSERT INTO report_updates (report_id,officer_id,note,status_changed_to,created_at) VALUES (%s,%s,%s,%s,%s)",
                    (rid, asgn, f"Case reviewed and status updated to {stat}.", stat, dt + timedelta(hours=2)))

conn.commit()
print(f"Created {len(report_ids)} reports")

# ── SOS Alerts ────────────────────────────────────────────────────
for i in range(6):
    cid  = random.choice(citizen_ids)
    stat = random.choice(["active","active","resolved"])
    dt   = datetime.now() - timedelta(hours=random.randint(0, 48))
    cur.execute("INSERT INTO sos_alerts (citizen_id,latitude,longitude,address,message,status,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (cid, -1.2921 + random.uniform(-0.05,0.05), 36.8219 + random.uniform(-0.05,0.05),
                 random.choice(locations), "Need immediate help!", stat, dt))
conn.commit()
print("Created SOS alerts")

# ── Safety Tips ───────────────────────────────────────────────────
tips = [
    ("Home Security","Secure your doors and windows","Always ensure all entry points are secured before leaving or sleeping. Use deadbolts and security bars on sliding doors.","bi-house-lock-fill",1),
    ("Home Security","Install security lighting","Motion-activated lights around your property deter intruders and make it safer to navigate at night.","bi-lightbulb-fill",2),
    ("Home Security","Know your neighbors","Building relationships with neighbors creates a community watch network. Share contact information and look out for each other.","bi-people-fill",3),
    ("Street Safety","Stay aware of your surroundings","Avoid using your phone while walking in public. Keep your head up and be aware of people around you.","bi-eye-fill",1),
    ("Street Safety","Avoid poorly lit areas at night","Stick to well-lit, busy streets when walking at night. Plan your route in advance.","bi-moon-stars-fill",2),
    ("Street Safety","Trust your instincts","If something feels wrong, it probably is. Remove yourself from uncomfortable situations.","bi-shield-check",3),
    ("Online Safety","Use strong passwords","Use unique, complex passwords for each account. Consider a password manager.","bi-key-fill",1),
    ("Online Safety","Beware of phishing","Never click suspicious links in emails or messages. Verify sender identity before sharing personal information.","bi-envelope-x-fill",2),
    ("Online Safety","Secure your WiFi","Use WPA3 encryption and change default router passwords. Avoid using public WiFi for sensitive transactions.","bi-wifi",3),
    ("Vehicle Safety","Never leave valuables visible","Remove bags, electronics, and valuables from your car. Thieves target vehicles with visible items.","bi-car-front-fill",1),
    ("Vehicle Safety","Park in well-lit areas","Choose busy, well-lit parking areas. Avoid isolated spots, especially at night.","bi-p-circle-fill",2),
    ("Vehicle Safety","Always lock your vehicle","Double-check that doors are locked and windows are closed every time you leave your vehicle.","bi-lock-fill",3),
    ("Emergency Contacts","Save emergency numbers","Keep police (999 or 112), fire brigade, and ambulance numbers saved in your phone.","bi-telephone-fill",1),
    ("Emergency Contacts","Know your local station","Find out the location and contact of your nearest police station.","bi-building-fill",2),
]
for cat,title,content,icon,sort in tips:
    cur.execute("INSERT INTO safety_tips (category,title,content,icon,sort_order) VALUES (%s,%s,%s,%s,%s)",
                (cat,title,content,icon,sort))
conn.commit()
print("Created safety tips")

cur.close(); conn.close()
print("\n✅ Seed complete!")
print("\n=== LOGIN CREDENTIALS ===")
print(f"Password for all officers: {OFFICER_PASSWORD}")
for oid, name, *_ in officers_data:
    print(f"  Officer  | ID: {oid:10} | {name}")
print("\nCitizen login — use any National ID below:")
for nid, name, *_ in citizens_data:
    print(f"  Citizen  | ID: {nid:12} | {name}")
print("\nOr enter ANY ID number to auto-register as a new citizen.")
