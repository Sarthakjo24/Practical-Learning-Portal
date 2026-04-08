import os
import pymysql
import sys

# Get password from dot env or just connect using known default
# MySQL80 uses root with no password on localhost usually, or check .env
from dotenv import load_dotenv
load_dotenv("backend/.env")

def main():
    db_url = os.environ.get("DATABASE_URL")
    if "root:root" in db_url:
        password = "root"
    else:
        password = ""
    
    conn = pymysql.connect(host="localhost", user="root", password=password, database="app_db")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT session_id, submission_time, count(a.answer_id) as answers, count(e.id) as evals 
            FROM candidate_sessions 
            LEFT JOIN candidate_answers a ON candidate_sessions.session_id = a.session_id 
            LEFT JOIN ai_evaluations e ON a.answer_id = e.answer_id 
            GROUP BY session_id
        """)
        for row in cur.fetchall():
            print(f"Session {row[0]}: submitted={row[1]}, answers={row[2]}, evals={row[3]}")

if __name__ == "__main__":
    main()
