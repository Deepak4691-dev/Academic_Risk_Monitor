"""Student Academic Performance & Risk Analysis System - Flask + Oracle FreeSQL."""
import os
from datetime import datetime

import oracledb
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

import db

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

# One row per student: average marks %, average attendance %, risk level and
# the latest stored recommendation. Rules follow the README:
#   marks < 40 AND attendance < 75  -> HIGH RISK
#   marks < 40 OR  attendance < 75  -> MEDIUM RISK
#   otherwise                       -> LOW RISK
STUDENT_STATS_SQL = """
WITH m AS (
    SELECT e.student_id,
           AVG(mk.marks_obtained / s.max_marks * 100) AS pct,
           SUM(mk.marks_obtained) AS total,
           SUM(s.max_marks)       AS max_total
    FROM marks mk
    JOIN enrollments e ON e.enrollment_id = mk.enrollment_id
    JOIN subjects s    ON s.subject_id    = mk.subject_id
    GROUP BY e.student_id
),
a AS (
    SELECT e.student_id,
           AVG(ar.attended_classes / ar.total_classes * 100) AS att
    FROM attendance ar
    JOIN enrollments e ON e.enrollment_id = ar.enrollment_id
    GROUP BY e.student_id
),
r AS (
    SELECT student_id, recommendation,
           ROW_NUMBER() OVER (PARTITION BY student_id
                              ORDER BY generated_date DESC, recommendation_id DESC) AS rn
    FROM student_recommendations
)
SELECT st.student_id, st.student_name, st.course, st.semester,
       ROUND(m.pct, 2) AS percentage,
       m.total, m.max_total,
       ROUND(a.att, 2) AS attendance_percentage,
       CASE
           WHEN m.pct IS NULL OR a.att IS NULL THEN 'NO DATA'
           WHEN m.pct < 40 AND a.att < 75      THEN 'HIGH RISK'
           WHEN m.pct < 40 OR  a.att < 75      THEN 'MEDIUM RISK'
           ELSE 'LOW RISK'
       END AS risk_level,
       r.recommendation
FROM students st
LEFT JOIN m ON m.student_id = st.student_id
LEFT JOIN a ON a.student_id = st.student_id
LEFT JOIN r ON r.student_id = st.student_id AND r.rn = 1
"""


def grade_for(pct):
    if pct is None:
        return "-"
    for cutoff, grade in ((80, "A"), (70, "B"), (60, "C"), (50, "D"), (40, "E")):
        if pct >= cutoff:
            return grade
    return "F"


def risk_class(level):
    return (level or "no data").split()[0].lower()


app.jinja_env.globals.update(grade_for=grade_for, risk_class=risk_class)


@app.errorhandler(oracledb.Error)
def database_error(err):
    return render_template("base.html", db_error=str(err)), 500


@app.route("/")
def dashboard():
    rows = db.query(STUDENT_STATS_SQL + " ORDER BY m.pct DESC NULLS LAST")
    scored = [r for r in rows if r["percentage"] is not None]
    summary = {
        "students": len(rows),
        "avg_marks": round(sum(r["percentage"] for r in scored) / len(scored), 2) if scored else None,
        "avg_att": round(sum(r["attendance_percentage"] for r in scored if r["attendance_percentage"] is not None)
                         / max(1, len([r for r in scored if r["attendance_percentage"] is not None])), 2) if scored else None,
        "high": sum(1 for r in rows if r["risk_level"] == "HIGH RISK"),
        "medium": sum(1 for r in rows if r["risk_level"] == "MEDIUM RISK"),
        "low": sum(1 for r in rows if r["risk_level"] == "LOW RISK"),
    }
    return render_template("dashboard.html", rows=rows, summary=summary)


@app.route("/students")
def students():
    rows = db.query(
        "SELECT student_id, student_name, email, course, semester, department, date_of_admission "
        "FROM students ORDER BY student_id"
    )
    return render_template("students.html", rows=rows)


@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        f = request.form
        try:
            params = {
                "name": f["student_name"].strip(),
                "email": f["email"].strip(),
                "course": f["course"].strip(),
                "semester": int(f["semester"]),
                "dept": f["department"].strip(),
                "adm": datetime.strptime(f["date_of_admission"], "%Y-%m-%d"),
            }
        except (KeyError, ValueError):
            flash("Check the form: every field is required and the semester must be a number.", "error")
            return render_template("add_student.html", form=f)

        # Works whether STUDENT_ID is an identity column or a plain number.
        try:
            db.execute(
                "INSERT INTO students (student_name, email, course, semester, department, date_of_admission) "
                "VALUES (:name, :email, :course, :semester, :dept, :adm)", params)
        except oracledb.DatabaseError as err:
            if "ORA-01400" in str(err):  # student_id is not auto-generated
                try:
                    db.execute(
                        "INSERT INTO students (student_id, student_name, email, course, semester, department, date_of_admission) "
                        "VALUES ((SELECT NVL(MAX(student_id), 0) + 1 FROM students), :name, :email, :course, :semester, :dept, :adm)",
                        params)
                except oracledb.DatabaseError as err2:
                    flash(f"Could not add student: {err2}", "error")
                    return render_template("add_student.html", form=f)
            elif "ORA-00001" in str(err):
                flash("A student with this email already exists.", "error")
                return render_template("add_student.html", form=f)
            else:
                flash(f"Could not add student: {err}", "error")
                return render_template("add_student.html", form=f)
        flash(f"Added {params['name']}.", "ok")
        return redirect(url_for("students"))
    return render_template("add_student.html", form={})


@app.route("/performance")
@app.route("/performance/<int:student_id>")
def performance(student_id=None):
    all_students = db.query("SELECT student_id, student_name FROM students ORDER BY student_name")
    if student_id is None and all_students:
        student_id = all_students[0]["student_id"]
    student, details = None, []
    if student_id is not None:
        found = db.query(STUDENT_STATS_SQL + " WHERE st.student_id = :sid", {"sid": student_id})
        student = found[0] if found else None
        details = db.query(
            """
            SELECT s.subject_name, mk.exam_type, mk.marks_obtained, s.max_marks, s.pass_marks,
                   ROUND(ar.attended_classes / ar.total_classes * 100, 1) AS attendance_pct
            FROM enrollments e
            JOIN marks mk    ON mk.enrollment_id = e.enrollment_id
            JOIN subjects s  ON s.subject_id     = mk.subject_id
            LEFT JOIN attendance ar ON ar.enrollment_id = e.enrollment_id AND ar.subject_id = mk.subject_id
            WHERE e.student_id = :sid
            ORDER BY s.subject_name
            """, {"sid": student_id})
    return render_template("performance.html", students=all_students, student=student,
                           details=details, selected=student_id)


@app.route("/risk")
def risk_report():
    rows = db.query(
        STUDENT_STATS_SQL +
        " ORDER BY CASE WHEN m.pct IS NULL OR a.att IS NULL THEN 4"
        "              WHEN m.pct < 40 AND a.att < 75 THEN 1"
        "              WHEN m.pct < 40 OR a.att < 75 THEN 2 ELSE 3 END, m.pct")
    return render_template("risk_report.html", rows=rows)


@app.route("/risk/generate", methods=["POST"])
def generate_recommendations():
    db.call_procedure("GENERATE_RECOMMENDATIONS")
    flash("Recommendations regenerated by the GENERATE_RECOMMENDATIONS procedure.", "ok")
    return redirect(url_for("risk_report"))


def insert_row(table, id_col, cols, params):
    """INSERT that works whether the ID column is auto-generated or not.
    table / id_col / cols are fixed names from this file, never user input."""
    names = ", ".join(cols)
    binds = ", ".join(f":{c}" for c in cols)
    try:
        db.execute(f"INSERT INTO {table} ({names}) VALUES ({binds})", params)
    except oracledb.DatabaseError as err:
        if "ORA-01400" not in str(err):
            raise
        db.execute(
            f"INSERT INTO {table} ({id_col}, {names}) VALUES "
            f"((SELECT NVL(MAX({id_col}), 0) + 1 FROM {table}), {binds})", params)


def db_message(err):
    """First line of an Oracle error, e.g. the text raised by the marks trigger."""
    return str(err).strip().splitlines()[0]


def enrollment_for(student_id):
    """Latest enrollment of the student; creates one if the student has none."""
    q = "SELECT MAX(enrollment_id) AS eid FROM enrollments WHERE student_id = :sid"
    rows = db.query(q, {"sid": student_id})
    if rows and rows[0]["eid"]:
        return rows[0]["eid"]
    semester = db.query("SELECT semester FROM students WHERE student_id = :sid", {"sid": student_id})[0]["semester"]
    # Reuse academic year and status already used by existing enrollments so
    # the table's own check constraints are satisfied.
    tmpl = db.query("SELECT academic_year, status FROM enrollments WHERE ROWNUM = 1")
    insert_row("enrollments", "enrollment_id",
               ["student_id", "academic_year", "semester", "enrollment_date", "status"],
               {"student_id": student_id,
                "academic_year": tmpl[0]["academic_year"] if tmpl else "2026-27",
                "semester": semester,
                "enrollment_date": datetime.now(),
                "status": tmpl[0]["status"] if tmpl else "ACTIVE"})
    return db.query(q, {"sid": student_id})[0]["eid"]


def student_and_subject_lists():
    return (db.query("SELECT student_id, student_name FROM students ORDER BY student_name"),
            db.query("SELECT subject_id, subject_name, max_marks FROM subjects ORDER BY subject_name"))


@app.route("/marks/add", methods=["GET", "POST"])
def add_marks():
    students_, subjects = student_and_subject_lists()
    f = request.form if request.method == "POST" else {"student_id": request.args.get("student_id", "")}
    if request.method == "POST":
        try:
            sid, sub = int(f["student_id"]), int(f["subject_id"])
            marks = float(f["marks_obtained"])
            exam = f["exam_type"].strip().upper()
            if not exam:
                raise ValueError
        except (KeyError, ValueError):
            flash("Choose a student and subject, and enter the marks as a number.", "error")
            return render_template("add_marks.html", students=students_, subjects=subjects, form=f)
        max_marks = next((s["max_marks"] for s in subjects if s["subject_id"] == sub), None)
        if max_marks is None or marks < 0 or marks > max_marks:
            flash(f"Marks must be between 0 and {max_marks or 'the subject maximum'}.", "error")
            return render_template("add_marks.html", students=students_, subjects=subjects, form=f)
        try:
            eid = enrollment_for(sid)
            key = {"e": eid, "s": sub, "x": exam}
            existing = db.query("SELECT mark_id FROM marks WHERE enrollment_id = :e AND subject_id = :s AND exam_type = :x", key)
            if existing:
                db.execute("UPDATE marks SET marks_obtained = :m, exam_date = :d WHERE mark_id = :id",
                           {"m": marks, "d": datetime.now(), "id": existing[0]["mark_id"]})
                flash("Marks updated.", "ok")
            else:
                insert_row("marks", "mark_id",
                           ["enrollment_id", "subject_id", "exam_type", "marks_obtained", "exam_date"],
                           {"enrollment_id": eid, "subject_id": sub, "exam_type": exam,
                            "marks_obtained": marks, "exam_date": datetime.now()})
                flash("Marks saved.", "ok")
        except oracledb.DatabaseError as err:
            flash(f"Could not save marks: {db_message(err)}", "error")
            return render_template("add_marks.html", students=students_, subjects=subjects, form=f)
        return redirect(url_for("performance", student_id=sid))
    return render_template("add_marks.html", students=students_, subjects=subjects, form=f)


@app.route("/attendance/add", methods=["GET", "POST"])
def add_attendance():
    students_, subjects = student_and_subject_lists()
    f = request.form if request.method == "POST" else {"student_id": request.args.get("student_id", "")}
    if request.method == "POST":
        try:
            sid, sub = int(f["student_id"]), int(f["subject_id"])
            total, attended = int(f["total_classes"]), int(f["attended_classes"])
        except (KeyError, ValueError):
            flash("Choose a student and subject, and enter the class counts as whole numbers.", "error")
            return render_template("add_attendance.html", students=students_, subjects=subjects, form=f)
        if total <= 0 or attended < 0 or attended > total:
            flash("Total classes must be positive and attended classes must be between 0 and the total.", "error")
            return render_template("add_attendance.html", students=students_, subjects=subjects, form=f)
        try:
            eid = enrollment_for(sid)
            existing = db.query("SELECT attendance_id FROM attendance WHERE enrollment_id = :e AND subject_id = :s",
                                {"e": eid, "s": sub})
            if existing:
                db.execute("UPDATE attendance SET total_classes = :t, attended_classes = :a, attendance_date = :d "
                           "WHERE attendance_id = :id",
                           {"t": total, "a": attended, "d": datetime.now(), "id": existing[0]["attendance_id"]})
                flash("Attendance updated.", "ok")
            else:
                insert_row("attendance", "attendance_id",
                           ["enrollment_id", "subject_id", "total_classes", "attended_classes", "attendance_date"],
                           {"enrollment_id": eid, "subject_id": sub, "total_classes": total,
                            "attended_classes": attended, "attendance_date": datetime.now()})
                flash("Attendance saved.", "ok")
        except oracledb.DatabaseError as err:
            flash(f"Could not save attendance: {db_message(err)}", "error")
            return render_template("add_attendance.html", students=students_, subjects=subjects, form=f)
        return redirect(url_for("performance", student_id=sid))
    return render_template("add_attendance.html", students=students_, subjects=subjects, form=f)


if __name__ == "__main__":
    app.run(debug=True)
