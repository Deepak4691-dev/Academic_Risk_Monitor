Student Academic Performance & Risk Analysis System
A web-based student academic management and risk analysis application built with Python Flask and Oracle FreeSQL. The system stores student details, records subject-wise marks and attendance, calculates academic performance, classifies students by risk level, and can regenerate recommendations through an Oracle stored procedure.
Features
- Dashboard: View the total number of students, average marks, average attendance, and counts of high-, medium-, and low-risk students.
- Student management: View student records and add new students.
- Performance tracking: View a selected student's overall performance and subject-wise marks and attendance.
- Marks management: Add marks for an exam or update an existing marks entry.
- Attendance management: Add attendance or update an existing attendance record.
- Risk analysis: Generate a risk report based on marks and attendance.
- Recommendations: Call the Oracle GENERATE_RECOMMENDATIONS stored procedure to regenerate student recommendations.
- Oracle database integration: Use python-oracledb in Thin mode to connect to Oracle FreeSQL.
Technology Stack
Technology	Purpose
Python	Application programming language
Flask	Web application framework and routing
Oracle FreeSQL	Relational database
python-oracledb	Python-to-Oracle database connectivity
python-dotenv	Load configuration values from .env
HTML / Jinja templates	Render the web pages


Risk Classification
The application calculates average marks percentage and average attendance percentage for each student. It then applies the following rule-based classification:
Condition	Risk level
Marks below 40% and attendance below 75%	HIGH RISK
Marks below 40% or attendance below 75%	MEDIUM RISK
Marks at least 40% and attendance at least 75%	LOW RISK
Marks or attendance data is unavailable	NO DATA


Note: The current implementation uses threshold-based rules in SQL. It is not a trained machine-learning prediction model.

Application Pages and Routes
Route	Description
/	Dashboard and student summary
/students	List students
/students/add	Add a student
/performance	View performance; selects the first student by default when available
/performance/<student_id>	View a particular student's performance
/marks/add	Add or update subject marks
/attendance/add	Add or update attendance
/risk	View the student risk report
/risk/generate	Regenerate recommendations using the Oracle procedure (POST request)


Database Requirements
The application expects an Oracle schema containing the following tables:
- STUDENTS
- SUBJECTS
- ENROLLMENTS
- MARKS
- ATTENDANCE
- STUDENT_RECOMMENDATIONS
It also expects an Oracle stored procedure named:
- GENERATE_RECOMMENDATIONS
The application code refers to columns including student details (student_id, student_name, email, course, semester, department, date_of_admission), subject details (subject_id, subject_name, max_marks, pass_marks), enrollment details, marks, attendance, and recommendation records.

Database setup scripts are not included in this repository's supplied application files. Create the tables, required constraints, and stored procedure in Oracle FreeSQL before running the application. The schema must match the SQL queries used in app.py.
Project Structure
A typical project layout is:
StudentAcademicSystem/
│
├── app.py
├── db.py
├── requirements.txt
├── .env.example
├── .env                  # Local secrets; do not commit
├── .gitignore
│
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── students.html
│   ├── add_student.html
│   ├── performance.html
│   ├── add_marks.html
│   ├── add_attendance.html
│   └── risk_report.html
│
└── static/               # CSS, JavaScript, images (if used)
The template and static filenames above describe the expected Flask layout; include the files that exist in your project.
Installation and Setup
1. Clone the repository
git clone https://github.com/YOUR_USERNAME/StudentAcademicSystem.git
cd StudentAcademicSystem
Replace YOUR_USERNAME with your GitHub username.
2. Create a virtual environment
py -m venv venv
Activate it in PowerShell:
.\venv\Scripts\Activate.ps1
If PowerShell blocks activation, you can either use Command Prompt activation:
venv\Scripts\activate.bat
or allow scripts for the current PowerShell process:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
3. Install dependencies
py -m pip install -r requirements.txt
4. Configure environment variables
Copy .env.example to .env:
Copy-Item .env.example .env
Open .env and enter the connection values from Oracle FreeSQL → Connect with Python:
ORACLE_USER=your_schema_username
ORACLE_PASSWORD=your_schema_password
ORACLE_DSN=tcps://your_host:your_port/your_service_name
FLASK_SECRET_KEY=replace_with_a_long_random_secret
Keep the real .env file private. It is excluded from Git by .gitignore. Never paste database passwords or secret keys into source code or commit them to GitHub.
5. Prepare the Oracle database
Sign in to Oracle FreeSQL using the schema configured in .env. Create the required tables and the GENERATE_RECOMMENDATIONS procedure before starting the Flask application.
6. Run the application
py app.py
Open the local address printed by Flask in your browser (normally):
http://127.0.0.1:5000/
Stop the development server with Ctrl + C.
How It Works
1. The Flask routes receive requests from the browser and render pages using Jinja templates.
2. The db.py module opens Oracle connections and provides helper functions for SELECT queries, data changes, and stored-procedure calls.
3. Student, marks, and attendance records are read from or written to Oracle tables.
4. SQL queries calculate average marks and attendance percentages.
5. The dashboard and risk report display the resulting risk categories.
6. The risk-generation route calls GENERATE_RECOMMENDATIONS and displays the latest stored recommendation for each student.
Validation and Error Handling
- Student form fields are checked, including numeric semester and admission date.
- Marks must be numeric and within the subject's maximum marks.
- Attendance must use a positive total class count, and attended classes cannot exceed total classes.
- Existing marks and attendance entries are updated rather than inserted as duplicates for the same enrollment and subject (and exam type for marks).
- Oracle database errors are handled and displayed through the application.
Security Notes
- Do not commit .env, passwords, database connection strings containing credentials, or production secret keys.
- Use a strong, randomly generated FLASK_SECRET_KEY.
- The built-in Flask development server and debug=True are for local development only. Use a production WSGI server and disable debug mode before deployment.
- Use test or anonymized student data when demonstrating the project publicly.
Future Enhancements
- Add charts and filters for academic trends.
- Add role-based login for administrators, faculty, and students.
- Export performance and risk reports to PDF or Excel.
- Add configurable risk thresholds.
- Explore a properly trained and evaluated machine-learning model using an appropriate, consented dataset.
