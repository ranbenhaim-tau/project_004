Run instructions (Windows):

1) Import the database (schema + data):
   sql/flytau_bigdata.sql

2) (Course requirement) Import the planning queries (Queries 1–5):
   sql/flytau_queries.sql

3) Install dependencies:
   pip install -r requirements.txt

4) Set environment variables (or use a .env file):
   FLYTAU_DB_HOST=localhost
   FLYTAU_DB_USER=root
   FLYTAU_DB_PASSWORD=YOUR_PASSWORD
   FLYTAU_DB_NAME=FLYTAU

5) Run:
   python main.py

Notes:
- Default Flask address: http://127.0.0.1:5000
- flytau_bigdata.sql recreates the schema (it runs DROP SCHEMA IF EXISTS FLYTAU).
