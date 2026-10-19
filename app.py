import os, io, csv, random, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from seating_logic import allocate_seats, normalize_roll_number

ROOT = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(ROOT, "instance"), exist_ok=True)
DB = os.path.join(ROOT, "instance", "seating.db")
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

def connect():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, roll_number TEXT);
        CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, roll_number TEXT UNIQUE NOT NULL, full_name TEXT DEFAULT '', department TEXT DEFAULT '', year TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS halls(id INTEGER PRIMARY KEY, hall_name TEXT UNIQUE NOT NULL, rows_count INTEGER NOT NULL, cols_count INTEGER NOT NULL, capacity INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS allocations(id INTEGER PRIMARY KEY, roll_number TEXT NOT NULL, full_name TEXT DEFAULT '', hall_name TEXT NOT NULL, seat_number TEXT NOT NULL, row_number INTEGER NOT NULL, col_number INTEGER NOT NULL, created_at TEXT NOT NULL);
        """)
        if not c.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            c.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)", ("admin",generate_password_hash("admin123"),"admin"))

def login_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("user_id"): return redirect(url_for("login"))
        return fn(*a, **k)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("user_id"): return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Administrator access required.", "error"); return redirect(url_for("dashboard"))
        return fn(*a, **k)
    return w

@app.context_processor
def globals_for_templates(): return {"current_year": datetime.now().year}

@app.route("/")
def index(): return redirect(url_for("dashboard" if session.get("user_id") else "login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        with connect() as c: u = c.execute("SELECT * FROM users WHERE username=?", (request.form.get("username","").strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password","")):
            session.clear(); session.update(user_id=u["id"], username=u["username"], role=u["role"], roll_number=u["roll_number"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username=request.form.get("username","").strip(); password=request.form.get("password",""); roll=normalize_roll_number(request.form.get("roll_number",""))
        if len(username)<3 or len(password)<6 or not roll: flash("Username must be 3+ characters, password 6+ characters, and roll number is required.", "error")
        else:
            with connect() as c:
                student=c.execute("SELECT roll_number FROM students WHERE roll_number=?", (roll,)).fetchone()
                exists=c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                if exists: flash("Username already exists.", "error")
                elif not student: flash("Ask the administrator to add your roll number first.", "error")
                else:
                    try:
                        c.execute("INSERT INTO users(username,password_hash,role,roll_number) VALUES(?,?,?,?)",(username,generate_password_hash(password),"student",roll))
                        flash("Registration successful. Please sign in.", "success"); return redirect(url_for("login"))
                    except sqlite3.IntegrityError: flash("Could not create account.", "error")
    return render_template("register.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with connect() as c:
        stats=[c.execute("SELECT COUNT(*) FROM students").fetchone()[0],c.execute("SELECT COUNT(*) FROM halls").fetchone()[0],c.execute("SELECT COUNT(*) FROM allocations").fetchone()[0]]
        halls=c.execute("SELECT * FROM halls ORDER BY hall_name").fetchall()
        latest=c.execute("SELECT * FROM allocations ORDER BY id DESC LIMIT 8").fetchall()
    return render_template("dashboard.html", stats=stats, halls=halls, latest=latest)

@app.route("/students", methods=["GET","POST"])
@admin_required
def students():
    if request.method=="POST":
        roll=normalize_roll_number(request.form.get("roll_number","")); name=request.form.get("full_name","").strip()
        dept=request.form.get("department","").strip(); year=request.form.get("year","").strip()
        if not roll: flash("Roll number is required.", "error")
        else:
            try:
                with connect() as c: c.execute("INSERT INTO students(roll_number,full_name,department,year) VALUES(?,?,?,?)",(roll,name,dept,year))
                flash("Student added.", "success")
            except sqlite3.IntegrityError: flash("That roll number already exists.", "error")
        return redirect(url_for("students"))
    q=request.args.get("q","").strip()
    with connect() as c:
        rows=c.execute("SELECT * FROM students WHERE roll_number LIKE ? OR full_name LIKE ? ORDER BY roll_number",(f"%{q}%",f"%{q}%")).fetchall()
    return render_template("students.html", students=rows, q=q)

@app.route("/students/import", methods=["POST"])
@admin_required
def import_students():
    f=request.files.get("file")
    if not f or not f.filename or not f.filename.lower().endswith((".csv",".xlsx")):
        flash("Upload a CSV or XLSX file.", "error"); return redirect(url_for("students"))
    try:
        import pandas as pd
        df=pd.read_csv(f) if f.filename.lower().endswith(".csv") else pd.read_excel(f)
        df.columns=[str(x).strip().lower().replace(" ","_") for x in df.columns]
        rc=next((x for x in ["roll_number","roll","roll_no","hall_ticket"] if x in df.columns),None)
        if not rc: flash("Required column: roll_number (also accepts roll, roll_no, hall_ticket).", "error"); return redirect(url_for("students"))
        added=skipped=0
        with connect() as c:
            for _,r in df.iterrows():
                roll=normalize_roll_number(r.get(rc,""))
                if not roll: skipped+=1; continue
                def val(keys):
                    col=next((k for k in keys if k in df.columns),None)
                    v=r.get(col,"") if col else ""
                    return "" if str(v).lower()=="nan" else str(v).strip()
                try:
                    c.execute("INSERT INTO students(roll_number,full_name,department,year) VALUES(?,?,?,?)",(roll,val(["full_name","name","student_name"]),val(["department","dept","branch"]),val(["year","class"])))
                    added+=1
                except sqlite3.IntegrityError: skipped+=1
        flash(f"Import complete: {added} added, {skipped} skipped.", "success")
    except Exception as e: flash(f"Could not read file: {e}", "error")
    return redirect(url_for("students"))

@app.route("/students/<int:sid>/delete", methods=["POST"])
@admin_required
def delete_student(sid):
    with connect() as c:
        s=c.execute("SELECT roll_number FROM students WHERE id=?", (sid,)).fetchone()
        if s:
            c.execute("DELETE FROM users WHERE roll_number=?", (s["roll_number"],)); c.execute("DELETE FROM allocations WHERE roll_number=?", (s["roll_number"],)); c.execute("DELETE FROM students WHERE id=?", (sid,))
    flash("Student deleted.", "success"); return redirect(url_for("students"))

@app.route("/halls", methods=["GET","POST"])
@admin_required
def halls():
    if request.method=="POST":
        name=request.form.get("hall_name","").strip()
        try: rows=int(request.form.get("rows_count",0)); cols=int(request.form.get("cols_count",0))
        except ValueError: rows=cols=0
        if not name or not (1<=rows<=100 and 1<=cols<=100): flash("Enter a hall name and row/column counts between 1 and 100.", "error")
        else:
            try:
                with connect() as c: c.execute("INSERT INTO halls(hall_name,rows_count,cols_count,capacity) VALUES(?,?,?,?)",(name,rows,cols,rows*cols))
                flash(f"Hall saved with {rows*cols} seats.", "success")
            except sqlite3.IntegrityError: flash("Hall name already exists.", "error")
        return redirect(url_for("halls"))
    with connect() as c: rows=c.execute("SELECT * FROM halls ORDER BY hall_name").fetchall()
    return render_template("halls.html", halls=rows)

@app.route("/halls/<int:hid>/delete", methods=["POST"])
@admin_required
def delete_hall(hid):
    with connect() as c:
        h=c.execute("SELECT hall_name FROM halls WHERE id=?", (hid,)).fetchone()
        if h: c.execute("DELETE FROM allocations WHERE hall_name=?", (h["hall_name"],)); c.execute("DELETE FROM halls WHERE id=?", (hid,))
    flash("Hall deleted.", "success"); return redirect(url_for("halls"))

@app.route("/allocate", methods=["POST"])
@admin_required
def allocate():
    with connect() as c:
        students=[dict(x) for x in c.execute("SELECT roll_number,full_name FROM students ORDER BY roll_number").fetchall()]
        halls=[dict(x) for x in c.execute("SELECT * FROM halls ORDER BY hall_name").fetchall()]
        if not students: flash("Add students before allocation.", "error"); return redirect(url_for("dashboard"))
        if not halls: flash("Add halls before allocation.", "error"); return redirect(url_for("halls"))
        if request.form.get("randomize"): random.shuffle(students)
        assigned,unassigned=allocate_seats(students,halls)
        c.execute("DELETE FROM allocations")
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.executemany("INSERT INTO allocations(roll_number,full_name,hall_name,seat_number,row_number,col_number,created_at) VALUES(?,?,?,?,?,?,?)",[(a["roll_number"],a["full_name"],a["hall_name"],a["seat_number"],a["row_number"],a["col_number"],now) for a in assigned])
    if unassigned: flash(f"Capacity exceeded: {len(unassigned)} student(s) remain unassigned. Add more seats.", "error")
    flash(f"Plan generated for {len(assigned)} student(s).", "success")
    return redirect(url_for("seating_plan"))

@app.route("/seating-plan")
@login_required
def seating_plan():
    with connect() as c:
        halls=c.execute("SELECT * FROM halls ORDER BY hall_name").fetchall()
        rows=c.execute("SELECT * FROM allocations ORDER BY hall_name,row_number,col_number").fetchall()
    grouped={}
    for r in rows: grouped.setdefault(r["hall_name"],[]).append(dict(r))
    return render_template("seating_plan.html", halls=halls, grouped=grouped)

@app.route("/myseat")
@login_required
def myseat():
    q=request.args.get("search","").strip()
    with connect() as c:
        if session.get("role")=="admin":
            rows=c.execute("SELECT * FROM allocations WHERE roll_number LIKE ? OR full_name LIKE ? ORDER BY hall_name,roll_number",(f"%{q}%",f"%{q}%")).fetchall()
        else: rows=c.execute("SELECT * FROM allocations WHERE roll_number=?",(session.get("roll_number"),)).fetchall()
    return render_template("myseat.html", allocations=rows, q=q)

@app.route("/export/students.csv")
@admin_required
def export_students():
    with connect() as c: rows=c.execute("SELECT roll_number,full_name,department,year FROM students ORDER BY roll_number").fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(["roll_number","full_name","department","year"])
    for r in rows: w.writerow(list(r))
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),mimetype="text/csv",as_attachment=True,download_name="students.csv")

@app.route("/export/seating.pdf")
@login_required
def export_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError:
        flash("Install requirements to enable PDF export.", "error"); return redirect(url_for("seating_plan"))
    with connect() as c: rows=c.execute("SELECT * FROM allocations ORDER BY hall_name,row_number,col_number").fetchall()
    if session.get("role")!="admin": rows=[r for r in rows if r["roll_number"]==session.get("roll_number")]
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
    data=[["Roll Number","Student Name","Hall","Seat","Row","Column"]]+[[r["roll_number"],r["full_name"],r["hall_name"],r["seat_number"],r["row_number"],r["col_number"]] for r in rows]
    table=Table(data,repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#243b53")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#cbd5e1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f1f5f9")]),("PADDING",(0,0),(-1,-1),7)]))
    doc.build([Paragraph("Exam Seating Allocation Plan",getSampleStyleSheet()["Title"]),Spacer(1,12),table]); buf.seek(0)
    return send_file(buf,mimetype="application/pdf",as_attachment=True,download_name="seating-plan.pdf")

init_db()
if __name__=="__main__": app.run(debug=True)
