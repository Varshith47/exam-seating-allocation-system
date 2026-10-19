# SeatWise — Exam Seating Allocation System

A Flask web app to manage student records, configure exam halls, automatically allocate seats, and view hall-wise seating plans.

TO run the project :- https://exam-seating-allocation-system.onrender.com/
## Features
- Admin and student login
- Add, search, import and export student records
- Import CSV or Excel (`.xlsx`)
- Configure halls by rows and columns
- Generate seating plans with optional randomized student order
- Hall-wise seat map and student-specific seat lookup
- Export the plan to PDF
- SQLite database created automatically
- Responsive dark UI

## Stack
Python, Flask, SQLite, HTML, CSS, Jinja, Pandas, OpenPyXL, ReportLab.

## Project structure
```text
exam_seating_allocation_system/
├── app.py
├── seating_logic.py
├── requirements.txt
├── README.md
├── .gitignore
├── instance/.gitkeep
├── sample_data/sample_students.csv
├── static/css/style.css
├── static/sample_students.csv
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── students.html
    ├── halls.html
    ├── seating_plan.html
    └── myseat.html
```

## Run on Windows
Open Command Prompt in the extracted project folder:
```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

If `py` is not available, use `python` instead.

## Default admin account
- Username: `admin`
- Password: `admin123`

Change the default password and set a strong `SECRET_KEY` before any real deployment. This is a development/demo application; do not expose the default account publicly.

## First use
1. Sign in as admin.
2. Add students manually or import the sample CSV.
3. Configure one or more exam halls.
4. Generate the seating plan from the dashboard.
5. Review the hall-wise plan and export it to PDF.
6. Students can register only after their roll number has been added by an administrator.

## Spreadsheet format
Required column: `roll_number` (also accepts `roll`, `roll_no`, or `hall_ticket`).
Optional columns: `full_name`, `department`, `year`.

Example:
```csv
roll_number,full_name,department,year
23CS001,Ananya Rao,CSE,3rd Year
23CS002,Rahul Kumar,CSE,3rd Year
23EC001,Sneha Reddy,ECE,3rd Year
```

## Allocation logic
Halls are processed alphabetically; seats are assigned row by row. Randomization shuffles the student list before assignment. If total hall capacity is too small, the app reports the number of students who could not be assigned. This starter version does not enforce institution-specific spacing constraints between students.

## Data and safety
The SQLite database is stored in `instance/seating.db` and excluded from Git. Do not commit real student records, passwords, or secret keys. Delete the local database file to reset demo data; it will be recreated at next launch.

## Author
Varshith Reddy Nimma · [GitHub @Varshith47](https://github.com/Varshith47)
"# exam-seating-allocation-system" 
