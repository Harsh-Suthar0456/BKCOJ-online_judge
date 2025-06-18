import os
import time
import csv
import subprocess
import json
import sqlite3
from typing import List, Dict, Any

# could put these in a config file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SUB_DIR = os.path.join(BASE_DIR, 'submissions')
CSV_FILE = os.path.join(BASE_DIR, 'submissions.csv')
PROB_DIR = os.path.join(BASE_DIR, 'problems')

DB_PATH = os.path.join(BASE_DIR, 'submissions.db')

# helper function
# def load_submissions():
#     with open(CSV_FILE, newline='') as f:
#         return list(csv.DictReader(f))

# helper function 
# def save_submissions(rows):
#     tmp = CSV_FILE + '.tmp'
#     with open(tmp, 'w', newline='') as f:
#         writer = csv.DictWriter(f, fieldnames=['id','problem','status','timestamp','userid'])
#         writer.writeheader()
#         writer.writerows(rows)
#     os.replace(tmp, CSV_FILE)
# def save_row(row):





############################ SQL DB FOR SUBMISSIONS ##########################################

# I did the implementation with .csv file, as submissions.csv, but it is not really
# efficient, and is also not easy to use for concurrent accesses, so the below 
# SQL code has just been take from chatGPT, cause me donno SQL bruh


def get_conn():
    """Return a SQLite connection in WAL mode for safe concurrent use."""
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute('PRAGMA journal_mode = WAL;')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Run once at startup to create the submissions table and status index."""
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id        TEXT    PRIMARY KEY,
                problem   TEXT    NOT NULL,
                status    TEXT    NOT NULL,
                timestamp TEXT    NOT NULL,
                userid    TEXT    NOT NULL
            );
        ''')
        # secondary index on status for fast lookups
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_submissions_status
            ON submissions(status);
        ''')


def load_pending() -> List[Dict[str, Any]]:
    """
    Fetch all submissions whose status is 'pending'.
    Returns a list of dicts.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, problem, status, timestamp, userid "
            "FROM submissions WHERE status = ?",
            ('pending',)
        )
        return [dict(row) for row in cur.fetchall()]


def get_submission(sub_id: str) -> Dict[str, Any]:
    """
    Fetch a single submission by its UUID hex.
    Returns a dict with keys: id, problem, status, timestamp, userid.
    Raises KeyError if no row matches.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, problem, status, timestamp, userid "
            "FROM submissions WHERE id = ?",
            (sub_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"No submission with id={sub_id}")
        return dict(row)


def update_submission(sub_id: str, **fields) -> None:
    """
    Update one or more columns on the given submission by its UUID hex.
    Usage: update_submission('a1b2c3...', status='running')
    Raises KeyError if no row matches.
    """
    if not fields:
        return

    # whitelist columns
    allowed = {'problem','status','timestamp','userid'}
    set_clauses = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Cannot update column '{k}'")
        set_clauses.append(f"{k} = ?")
        vals.append(v)
    vals.append(sub_id)

    sql = f"UPDATE submissions SET {', '.join(set_clauses)} WHERE id = ?"
    with get_conn() as conn:
        conn.execute('BEGIN;')
        cur = conn.execute(sql, vals)
        if cur.rowcount == 0:
            conn.execute('ROLLBACK;')
            raise KeyError(f"No submission with id={sub_id}")
        conn.execute('COMMIT;')


##############################################################################################








###################################### CHECKER ###############################################


init_db()
while True:

    # Could improve performance here by somehow only looping over submissions that are
    # pending, and not those which have been processed, but can't figure out how to do that for 
    # now. 
    # rows = load_submissions()
    rows = load_pending()
    for row in rows:
        if row['status'] != 'pending':
            continue
        sub_id = row['id']

        # 'running' in CSV
        row['status'] = 'running'
        # save_row(row)
        update_submission(sub_id, status='running')

        sub_path = os.path.join(SUB_DIR, sub_id)
        pid = row['problem']
        tests_dir = os.path.join(PROB_DIR, pid, 'tests')

        # config for the problem
        config_file = os.path.join(PROB_DIR, pid, 'config.json')
        if not os.path.exists(config_file):
            TIME_LIMIT = 2
            MEMORY_LIMIT = 256
        else:
            with open(config_file) as f:
                config = json.load(f)
            TIME_LIMIT = config.get('TIME_LIMIT', 2)
            MEMORY_LIMIT = config.get('MEMORY_LIMIT', 256)

        # get total testcases beforehand, else issues with compiling etc.
        if not os.path.exists(tests_dir):
            total = 0
        else:
            total = len([f for f in os.listdir(tests_dir) if f.startswith('input') and f.endswith('.txt')])
        

        passed = 0

        # compile
        comp = subprocess.run([
            'docker','run','--rm','--network','none',
            '-v',f"{sub_path}:/usr/src:rw",
            'code-runner:latest',
            'bash','-c','g++ /usr/src/main.cpp -O2 -o /usr/src/main'
        ], capture_output=True, text=True)
        if comp.returncode != 0:
            result = f"Compile Error:{comp.stderr or comp.stdout}"
        else:
            # execute each test with {TIME_LIMIT}s timeout and {MEMORY_LIMIT}MB memory limit
            # passed = 0
            result = f"Running tests for {pid}:\n"

            if os.path.exists(tests_dir):
                for fn in sorted(os.listdir(tests_dir)):
                    if not fn.startswith('input') or not fn.endswith('.txt'):
                        continue
                    idx = fn[len('input'):-4]
                    # total += 1
                    proc = subprocess.run([
                        'docker','run','--rm','--network','none',
                        '-m',f'{MEMORY_LIMIT}m','--cpus','0.5',
                        '-v',f"{sub_path}:/usr/src:rw",
                        '-v',f"{tests_dir}:/tests:ro",
                        'code-runner:latest',
                        'bash','-c',f"timeout {TIME_LIMIT}s /usr/src/main < /tests/input{idx}.txt > /usr/src/actual{idx}.txt"
                    ], capture_output=True, text=True)

                    # check timeout or memory limit separately
                    if proc.returncode == 124:
                        result += f"Test {idx} timed out after {TIME_LIMIT}s.\n"
                        continue
                    elif proc.returncode == 137:
                        result += f"Test {idx} exceeded memory limit of {MEMORY_LIMIT}MB.\n"
                        continue
                    elif proc.returncode != 0:
                        result += f"Unexpected error on Test {idx}, other than timeout and memory limit exceeded\n"
                    
                    ####### can replace below code with any general checking script #####################

                    # token checker
                    exp = open(os.path.join(tests_dir,f'output{idx}.txt')).read().split()
                    act = open(os.path.join(sub_path,f'actual{idx}.txt')).read().split()
                    if act == exp:
                        passed += 1
                        result += f"Test {idx} passed.\n"
                    else:
                        result += f"Wrong answer on Test{idx}\n"
                    
                    #####################################################################################

            result += f"Passed {passed}/{total} tests."

        # write result and mark 'completed'
        open(os.path.join(sub_path,'result.txt'),'w').write(result)

        if(passed == total):
            row['status'] = 'accepted'
        else:
            row['status'] = 'failed'
        
        # save_submissions(rows)
        update_submission(sub_id, status=row['status'])

        # remove the binary file
        binary_path = os.path.join(sub_path, 'main')
        if os.path.exists(binary_path):
            os.remove(binary_path)

        # could also remove the code outputs, but maybe keep for when debugging on hidden testcases
        # is allowed. will think later
        
    time.sleep(5)



##############################################################################################