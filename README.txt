FLYTAU (Group 004) - Run & Deployment Instructions

This project runs on SQLite (PythonAnywhere compatible). The database file is created locally as `flytau.db`.

Local run (Mac/Linux/Windows):

1) Install dependencies:
   pip install -r requirements.txt

2) Create / reset the SQLite DB (schema + data):
   python seed_data.py

   This creates `flytau.db` in the project directory, using:
   - sql/flytau_schema.sql
   - sql/flytau_data.sql

3) (Optional) Add performance indexes (safe to run multiple times):
   python optimize_db.py

4) Run the app:
   python main.py

5) Open in browser:
   http://127.0.0.1:5000

Course files:
- sql/flytau_queries.sql: planning queries (Queries 1–5) required in the written submission (Group_XX.pdf).

PythonAnywhere deployment (summary):

1) Bash console:
   git clone https://github.com/ranbenhaim-tau/project_004.git mysite
   cd mysite
   pip3.10 install --user -r requirements.txt
   python3.10 seed_data.py
   python3.10 optimize_db.py

2) Web tab:
   - Add a new web app (Manual configuration, Python 3.10)
   - Set source code to: /home/<yourusername>/mysite
   - Edit the WSGI file to import the Flask app:

     import sys
     project_home = '/home/<yourusername>/mysite'
     if project_home not in sys.path:
         sys.path.insert(0, project_home)
     from main import app as application

3) Reload the web app after every pull:
   Web tab -> Reload

Updating the online site after changes:
1) cd ~/mysite
2) git pull origin main
3) (only if SQL/schema/data changed) python3.10 seed_data.py
4) python3.10 optimize_db.py
5) Web tab -> Reload
