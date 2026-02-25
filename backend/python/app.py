from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2, psycopg2.extras, os, random, string
from datetime import timedelta, datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "crime-system-jwt-secret-2024")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
jwt = JWTManager(app)


# ─── DB ────────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "crime_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def q(sql, params=(), one=False, many=False, commit=False):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute(sql, params)
        r = cur.fetchone() if one else (cur.fetchall() if many else None)
        if commit: conn.commit()
        return r
    finally:
        cur.close(); conn.close()


# ─── HELPERS ───────────────────────────────────────────────────────
def gen_ref():
    return "REF-" + "".join(random.choices(string.digits, k=8))


# ══════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════

@app.route("/api/auth/officer/login", methods=["POST"])
def officer_login():
    d = request.get_json()
    officer_id = (d.get("officer_id") or "").strip().upper()
    password   = d.get("password") or ""
    officer = q("SELECT * FROM officers WHERE officer_id=%s AND is_active=true", (officer_id,), one=True)
    if not officer or not check_password_hash(officer["password_hash"], password):
        return jsonify({"error": "Invalid Officer ID or password"}), 401
    token = create_access_token(
        identity=str(officer["id"]),
        additional_claims={"role": "officer", "officer_id": officer["officer_id"]}
    )
    return jsonify({
        "token": token,
        "officer": {
            "id": officer["id"],
            "officer_id": officer["officer_id"],
            "name": officer["name"],
            "rank": officer["rank"],
            "department": officer["department"],
            "station": officer["station"],
            "badge_number": officer["badge_number"]
        }
    })


@app.route("/api/auth/citizen/login", methods=["POST"])
def citizen_login():
    """Login with national ID number — creates citizen record if not exists"""
    d = request.get_json()
    national_id = (d.get("national_id") or "").strip().upper()
    if not national_id or len(national_id) < 4:
        return jsonify({"error": "Please enter a valid ID number"}), 400

    citizen = q("SELECT * FROM citizens WHERE national_id=%s", (national_id,), one=True)
    if not citizen:
        # Auto-register citizen on first login
        citizen = q(
            "INSERT INTO citizens (national_id, display_name) VALUES (%s,%s) RETURNING *",
            (national_id, f"Citizen {national_id[-4:]}"), one=True, commit=True
        )

    token = create_access_token(
        identity=str(citizen["id"]),
        additional_claims={"role": "citizen", "national_id": citizen["national_id"]}
    )
    return jsonify({
        "token": token,
        "citizen": {
            "id": citizen["id"],
            "national_id": citizen["national_id"],
            "display_name": citizen["display_name"],
            "phone": citizen["phone"],
            "email": citizen["email"]
        }
    })


@app.route("/api/auth/me", methods=["GET"])
@jwt_required()
def get_me():
    claims = get_jwt()
    uid    = get_jwt_identity()
    role   = claims.get("role")
    if role == "officer":
        r = q("SELECT id,officer_id,name,rank,department,station,badge_number FROM officers WHERE id=%s", (uid,), one=True)
        return jsonify({"role": "officer", **dict(r)}) if r else (jsonify({"error": "Not found"}), 404)
    else:
        r = q("SELECT id,national_id,display_name,phone,email FROM citizens WHERE id=%s", (uid,), one=True)
        return jsonify({"role": "citizen", **dict(r)}) if r else (jsonify({"error": "Not found"}), 404)


# ══════════════════════════════════════════════════════════════════
#  CITIZEN PORTAL
# ══════════════════════════════════════════════════════════════════

@app.route("/api/citizen/profile", methods=["PUT"])
@jwt_required()
def update_citizen_profile():
    uid = get_jwt_identity()
    d   = request.get_json()
    allowed = ["display_name", "phone", "email"]
    fields  = {k: v for k, v in d.items() if k in allowed}
    if not fields: return jsonify({"error": "No valid fields"}), 400
    q(f"UPDATE citizens SET {', '.join(f'{k}=%s' for k in fields)} WHERE id=%s",
      list(fields.values()) + [uid], commit=True)
    return jsonify({"message": "Profile updated"})


@app.route("/api/citizen/dashboard", methods=["GET"])
@jwt_required()
def citizen_dashboard():
    uid = get_jwt_identity()
    reports      = q("SELECT COUNT(*) as n FROM reports WHERE citizen_id=%s", (uid,), one=True)["n"]
    pending      = q("SELECT COUNT(*) as n FROM reports WHERE citizen_id=%s AND status='pending'", (uid,), one=True)["n"]
    under_review = q("SELECT COUNT(*) as n FROM reports WHERE citizen_id=%s AND status='under_review'", (uid,), one=True)["n"]
    resolved     = q("SELECT COUNT(*) as n FROM reports WHERE citizen_id=%s AND status='resolved'", (uid,), one=True)["n"]
    recent       = q("SELECT id,reference_number,crime_type,status,created_at,is_anonymous FROM reports WHERE citizen_id=%s ORDER BY created_at DESC LIMIT 5", (uid,), many=True)
    return jsonify({
        "stats": {"total": reports, "pending": pending, "under_review": under_review, "resolved": resolved},
        "recent_reports": [dict(r) for r in (recent or [])]
    })


@app.route("/api/citizen/reports", methods=["GET"])
@jwt_required()
def get_citizen_reports():
    uid    = get_jwt_identity()
    status = request.args.get("status", "")
    conds  = ["citizen_id=%s"]; params = [uid]
    if status: conds.append("status=%s"); params.append(status)
    where  = " AND ".join(conds)
    rows   = q(f"SELECT * FROM reports WHERE {where} ORDER BY created_at DESC", params, many=True)
    return jsonify([dict(r) for r in (rows or [])])


@app.route("/api/citizen/reports", methods=["POST"])
@jwt_required()
def submit_named_report():
    """Named report — citizen is logged in and identified"""
    uid = get_jwt_identity()
    d   = request.get_json()
    ref = gen_ref()
    citizen = q("SELECT national_id, display_name FROM citizens WHERE id=%s", (uid,), one=True)
    r = q("""
        INSERT INTO reports
          (reference_number, citizen_id, is_anonymous,
           crime_type, description, location, incident_date,
           incident_time, county, sub_county, suspect_info,
           witness_info, status)
        VALUES (%s,%s,false,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
        RETURNING id, reference_number
    """, (ref, uid, d.get("crime_type","Other"), d["description"],
          d.get("location",""), d.get("incident_date"), d.get("incident_time",""),
          d.get("county",""), d.get("sub_county",""),
          d.get("suspect_info",""), d.get("witness_info","")),
        one=True, commit=True)
    return jsonify(dict(r)), 201


@app.route("/api/citizen/reports/anonymous", methods=["POST"])
def submit_anonymous_report():
    """Anonymous report — no auth required"""
    d   = request.get_json()
    ref = gen_ref()
    r = q("""
        INSERT INTO reports
          (reference_number, citizen_id, is_anonymous,
           crime_type, description, location, incident_date,
           incident_time, county, sub_county, suspect_info,
           witness_info, status)
        VALUES (%s, NULL, true, %s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
        RETURNING id, reference_number
    """, (ref, d.get("crime_type","Other"), d["description"],
          d.get("location",""), d.get("incident_date"), d.get("incident_time",""),
          d.get("county",""), d.get("sub_county",""),
          d.get("suspect_info",""), d.get("witness_info","")),
        one=True, commit=True)
    return jsonify({**dict(r), "message": "Report submitted anonymously"}), 201


@app.route("/api/citizen/reports/<int:rid>", methods=["GET"])
@jwt_required()
def get_citizen_report_detail(rid):
    uid = get_jwt_identity()
    r   = q("SELECT * FROM reports WHERE id=%s AND citizen_id=%s", (rid, uid), one=True)
    if not r: return jsonify({"error": "Not found"}), 404
    updates = q("SELECT * FROM report_updates WHERE report_id=%s ORDER BY created_at DESC", (rid,), many=True)
    return jsonify({"report": dict(r), "updates": [dict(u) for u in (updates or [])]})


@app.route("/api/citizen/sos", methods=["POST"])
@jwt_required()
def send_sos():
    uid = get_jwt_identity()
    d   = request.get_json()
    r   = q("""
        INSERT INTO sos_alerts (citizen_id, latitude, longitude, address, message, status)
        VALUES (%s,%s,%s,%s,%s,'active') RETURNING id, created_at
    """, (uid, d.get("latitude"), d.get("longitude"), d.get("address",""), d.get("message","")),
        one=True, commit=True)
    return jsonify({"id": r["id"], "message": "SOS alert sent! Officers have been notified.", "created_at": str(r["created_at"])}), 201


@app.route("/api/safety-tips", methods=["GET"])
def get_safety_tips():
    category = request.args.get("category", "")
    if category:
        rows = q("SELECT * FROM safety_tips WHERE category=%s AND is_active=true ORDER BY sort_order", (category,), many=True)
    else:
        rows = q("SELECT * FROM safety_tips WHERE is_active=true ORDER BY category, sort_order", many=True)
    return jsonify([dict(r) for r in (rows or [])])


# ══════════════════════════════════════════════════════════════════
#  OFFICER PORTAL
# ══════════════════════════════════════════════════════════════════

def officer_only():
    claims = get_jwt()
    return claims.get("role") == "officer"


@app.route("/api/officer/dashboard", methods=["GET"])
@jwt_required()
def officer_dashboard():
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid = get_jwt_identity()

    total       = q("SELECT COUNT(*) as n FROM reports", one=True)["n"]
    pending     = q("SELECT COUNT(*) as n FROM reports WHERE status='pending'", one=True)["n"]
    under_rev   = q("SELECT COUNT(*) as n FROM reports WHERE status='under_review'", one=True)["n"]
    resolved    = q("SELECT COUNT(*) as n FROM reports WHERE status='resolved'", one=True)["n"]
    dismissed   = q("SELECT COUNT(*) as n FROM reports WHERE status='dismissed'", one=True)["n"]
    my_cases    = q("SELECT COUNT(*) as n FROM reports WHERE assigned_officer_id=%s", (uid,), one=True)["n"]
    sos_active  = q("SELECT COUNT(*) as n FROM sos_alerts WHERE status='active'", one=True)["n"]

    # Crime type breakdown
    by_type = q("""
        SELECT crime_type, COUNT(*) as cnt
        FROM reports GROUP BY crime_type ORDER BY cnt DESC LIMIT 8
    """, many=True)

    # Monthly trend (last 6 months)
    trend = q("""
        SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'Mon YYYY') as month,
               COUNT(*) as count
        FROM reports
        WHERE created_at >= NOW() - INTERVAL '6 months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY DATE_TRUNC('month', created_at)
    """, many=True)

    # Status breakdown for donut
    by_status = q("""
        SELECT status, COUNT(*) as cnt FROM reports GROUP BY status
    """, many=True)

    # County breakdown
    by_county = q("""
        SELECT county, COUNT(*) as cnt FROM reports
        WHERE county != '' GROUP BY county ORDER BY cnt DESC LIMIT 6
    """, many=True)

    # Recent reports
    recent = q("""
        SELECT r.id, r.reference_number, r.crime_type, r.status, r.priority,
               r.location, r.county, r.is_anonymous, r.created_at,
               c.national_id, c.display_name,
               o.name as assigned_officer_name
        FROM reports r
        LEFT JOIN citizens c ON r.citizen_id = c.id
        LEFT JOIN officers o ON r.assigned_officer_id = o.id
        ORDER BY r.created_at DESC LIMIT 8
    """, many=True)

    return jsonify({
        "stats": {
            "total": total, "pending": pending, "under_review": under_rev,
            "resolved": resolved, "dismissed": dismissed,
            "my_cases": my_cases, "sos_active": sos_active
        },
        "by_type": [dict(r) for r in (by_type or [])],
        "monthly_trend": [dict(r) for r in (trend or [])],
        "by_status": [dict(r) for r in (by_status or [])],
        "by_county": [dict(r) for r in (by_county or [])],
        "recent_reports": [dict(r) for r in (recent or [])]
    })


@app.route("/api/officer/cases", methods=["GET"])
@jwt_required()
def officer_cases():
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid      = get_jwt_identity()
    status   = request.args.get("status", "")
    priority = request.args.get("priority", "")
    crime    = request.args.get("crime_type", "")
    search   = request.args.get("search", "")
    assigned = request.args.get("assigned_to_me", "")
    page     = max(1, int(request.args.get("page", 1)))
    limit    = int(request.args.get("limit", 12))
    offset   = (page - 1) * limit

    conds = []; params = []
    if status:   conds.append("r.status=%s");       params.append(status)
    if priority: conds.append("r.priority=%s");     params.append(priority)
    if crime:    conds.append("r.crime_type=%s");   params.append(crime)
    if assigned == "1": conds.append("r.assigned_officer_id=%s"); params.append(uid)
    if search:
        conds.append("(r.reference_number ILIKE %s OR r.description ILIKE %s OR r.location ILIKE %s OR r.crime_type ILIKE %s)")
        params.extend([f"%{search}%"] * 4)

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    total = q(f"SELECT COUNT(*) as n FROM reports r {where}", params, one=True)["n"]
    rows  = q(f"""
        SELECT r.*, c.national_id, c.display_name as citizen_name,
               o.name as assigned_officer_name, o.officer_id as assigned_officer_code
        FROM reports r
        LEFT JOIN citizens c ON r.citizen_id = c.id
        LEFT JOIN officers o ON r.assigned_officer_id = o.id
        {where}
        ORDER BY
          CASE r.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
          r.created_at DESC
        LIMIT %s OFFSET %s
    """, params + [limit, offset], many=True)

    return jsonify({
        "cases": [dict(r) for r in (rows or [])],
        "total": total, "page": page,
        "pages": max(1, (total + limit - 1) // limit)
    })


@app.route("/api/officer/cases/<int:rid>", methods=["GET"])
@jwt_required()
def officer_case_detail(rid):
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    r = q("""
        SELECT r.*, c.national_id, c.display_name as citizen_name, c.phone as citizen_phone,
               o.name as assigned_officer_name, o.officer_id as assigned_officer_code, o.rank as assigned_rank
        FROM reports r
        LEFT JOIN citizens c ON r.citizen_id = c.id
        LEFT JOIN officers o ON r.assigned_officer_id = o.id
        WHERE r.id=%s
    """, (rid,), one=True)
    if not r: return jsonify({"error": "Not found"}), 404
    updates = q("SELECT u.*, o.name as officer_name FROM report_updates u LEFT JOIN officers o ON u.officer_id=o.id WHERE u.report_id=%s ORDER BY u.created_at DESC", (rid,), many=True)
    return jsonify({"case": dict(r), "updates": [dict(u) for u in (updates or [])]})


@app.route("/api/officer/cases/<int:rid>", methods=["PUT"])
@jwt_required()
def update_case(rid):
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid = get_jwt_identity()
    d   = request.get_json()
    allowed = ["status", "priority", "assigned_officer_id", "officer_notes", "case_number"]
    fields  = {k: v for k, v in d.items() if k in allowed}
    if not fields: return jsonify({"error": "No valid fields"}), 400
    q(f"UPDATE reports SET {', '.join(f'{k}=%s' for k in fields)}, updated_at=NOW() WHERE id=%s",
      list(fields.values()) + [rid], commit=True)
    # Add update log
    if "status" in fields or d.get("note"):
        note_text = d.get("note") or f"Status changed to: {fields.get('status', 'updated')}"
        q("INSERT INTO report_updates (report_id, officer_id, note, status_changed_to) VALUES (%s,%s,%s,%s)",
          (rid, uid, note_text, fields.get("status")), commit=True)
    return jsonify({"message": "Case updated"})


@app.route("/api/officer/cases/<int:rid>/note", methods=["POST"])
@jwt_required()
def add_case_note(rid):
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid = get_jwt_identity()
    d   = request.get_json()
    q("INSERT INTO report_updates (report_id, officer_id, note, status_changed_to) VALUES (%s,%s,%s,%s)",
      (rid, uid, d["note"], d.get("status_changed_to")), commit=True)
    return jsonify({"message": "Note added"}), 201


@app.route("/api/officer/cases/<int:rid>/assign", methods=["POST"])
@jwt_required()
def assign_case(rid):
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid = get_jwt_identity()
    d   = request.get_json()
    officer_id = d.get("officer_id", uid)
    q("UPDATE reports SET assigned_officer_id=%s, status='under_review', updated_at=NOW() WHERE id=%s",
      (officer_id, rid), commit=True)
    o = q("SELECT name FROM officers WHERE id=%s", (officer_id,), one=True)
    q("INSERT INTO report_updates (report_id, officer_id, note, status_changed_to) VALUES (%s,%s,%s,'under_review')",
      (rid, uid, f"Case assigned to {o['name'] if o else 'officer'}"), commit=True)
    return jsonify({"message": "Case assigned"})


@app.route("/api/officer/analytics", methods=["GET"])
@jwt_required()
def officer_analytics():
    if not officer_only(): return jsonify({"error": "Officers only"}), 403

    # Monthly reports last 12 months
    monthly = q("""
        SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'Mon') as month,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE status='resolved') as resolved,
               COUNT(*) FILTER (WHERE status='pending') as pending
        FROM reports
        WHERE created_at >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY DATE_TRUNC('month', created_at)
    """, many=True)

    # Crime types
    by_type = q("""
        SELECT crime_type, COUNT(*) as cnt,
               ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM reports), 0), 1) as pct
        FROM reports GROUP BY crime_type ORDER BY cnt DESC
    """, many=True)

    # County heatmap
    by_county = q("""
        SELECT county, COUNT(*) as cnt FROM reports
        WHERE county != '' GROUP BY county ORDER BY cnt DESC
    """, many=True)

    # Officer performance
    officers_perf = q("""
        SELECT o.name, o.officer_id, o.rank,
               COUNT(r.id) as total_cases,
               COUNT(r.id) FILTER (WHERE r.status='resolved') as resolved,
               COUNT(r.id) FILTER (WHERE r.status='pending') as pending
        FROM officers o
        LEFT JOIN reports r ON r.assigned_officer_id = o.id
        GROUP BY o.id, o.name, o.officer_id, o.rank
        ORDER BY total_cases DESC
    """, many=True)

    # Resolution time avg (days)
    resolution = q("""
        SELECT AVG(EXTRACT(epoch FROM (updated_at - created_at))/86400)::numeric(10,1) as avg_days
        FROM reports WHERE status='resolved'
    """, one=True)

    # Peak hours
    by_hour = q("""
        SELECT EXTRACT(HOUR FROM created_at)::int as hour, COUNT(*) as cnt
        FROM reports GROUP BY hour ORDER BY hour
    """, many=True)

    # Weekly pattern
    by_weekday = q("""
        SELECT TO_CHAR(created_at, 'Dy') as day, COUNT(*) as cnt
        FROM reports GROUP BY TO_CHAR(created_at, 'Dy'), EXTRACT(DOW FROM created_at)
        ORDER BY EXTRACT(DOW FROM created_at)
    """, many=True)

    return jsonify({
        "monthly": [dict(r) for r in (monthly or [])],
        "by_type": [dict(r) for r in (by_type or [])],
        "by_county": [dict(r) for r in (by_county or [])],
        "officers_performance": [dict(r) for r in (officers_perf or [])],
        "avg_resolution_days": float(resolution["avg_days"]) if resolution and resolution["avg_days"] else 0,
        "by_hour": [dict(r) for r in (by_hour or [])],
        "by_weekday": [dict(r) for r in (by_weekday or [])]
    })


@app.route("/api/officer/sos", methods=["GET"])
@jwt_required()
def get_sos_alerts():
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    rows = q("""
        SELECT s.*, c.national_id, c.display_name, c.phone
        FROM sos_alerts s
        LEFT JOIN citizens c ON s.citizen_id = c.id
        ORDER BY s.created_at DESC LIMIT 50
    """, many=True)
    return jsonify([dict(r) for r in (rows or [])])


@app.route("/api/officer/sos/<int:sid>/resolve", methods=["POST"])
@jwt_required()
def resolve_sos(sid):
    if not officer_only(): return jsonify({"error": "Officers only"}), 403
    uid = get_jwt_identity()
    q("UPDATE sos_alerts SET status='resolved', resolved_by=%s, resolved_at=NOW() WHERE id=%s",
      (uid, sid), commit=True)
    return jsonify({"message": "SOS resolved"})


@app.route("/api/officers", methods=["GET"])
@jwt_required()
def get_officers():
    rows = q("SELECT id,officer_id,name,rank,department,station FROM officers WHERE is_active=true ORDER BY name", many=True)
    return jsonify([dict(r) for r in (rows or [])])


@app.route("/api/health", methods=["GET"])
def health(): return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
