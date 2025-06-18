import os
import uuid
import csv
from datetime import datetime
import json
from flask import Flask, render_template, request, url_for, send_from_directory, redirect, flash
# user login imports
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from typing import List, Dict, Any

app =Flask(__name__)
BASE_DIR =os.path.abspath(os.path.dirname(__file__))
SUB_DIR =os.path.join(BASE_DIR, 'submissions')

CSV_FILE =os.path.join(BASE_DIR, 'submissions.csv') # .csv as database for submission has been ditched

PROB_DIR =os.path.join(BASE_DIR, 'problems')
DB_PATH = os.path.join(BASE_DIR, 'submissions.db')


# something related to flask, donno what it does tho, required
app.secret_key = os.environ.get("SECRET_KEY", "BKCOJ-is-the-GOAT")

# Set up subs
os.makedirs(SUB_DIR, exist_ok=True) # leave if exists

# if not os.path.exists(CSV_FILE):
#     with open(CSV_FILE,'w',newline='') as f:
#         writer = csv.writer(f)
#         writer.writerow(['id','problem','status','timestamp','user_id'])






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


def load_all_subs_for_curr_user() -> List[Dict[str, Any]]:
    """
    Fetch all submissions.
    Returns a list of dicts.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, problem, status, timestamp, userid FROM submissions "
            "WHERE userid = ?",
            (current_user.id, )
        )
        return [dict(row) for row in cur.fetchall()]


def add_submission(sub_id: str, problem: str, userid: str,
                   status: str = 'pending',
                   timestamp: str = None) -> str:
    """
    Insert a new submission with a UUID4 hex key.
    Returns the new row's id (hex string).
    If `timestamp` is None, uses CURRENT_TIMESTAMP.
    """
    new_id = sub_id if sub_id else uuid.uuid4().hex
    with get_conn() as conn:
        if timestamp is None:
            conn.execute(
                "INSERT INTO submissions (id, problem, status, userid, timestamp) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (new_id, problem, status, userid)
            )
        else:
            conn.execute(
                "INSERT INTO submissions (id, problem, status, userid, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (new_id, problem, status, userid, timestamp)
            )
    return new_id

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

def empty_db():
    """
    Empty the submissions table.
    Useful for testing or resetting the database.
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("VACUUM")  # clean up space

def delete_submission(sub_id: str) -> None:
    """
    Delete a submission by its UUID hex.
    Raises KeyError if no row matches.
    """
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
        if cur.rowcount == 0:
            raise KeyError(f"No submission with id={sub_id}")


##############################################################################################








####################################### WEB PAGES ############################################


# the home page stuff
@app.route('/')
@login_required
def index():
    # init db if not done already
    init_db()
    # empty_db() # for testing, remove this line in production

    # Previous subs loaded
    # submissions=[]
    # with open(CSV_FILE, newline='') as f:
    #     reader=csv.DictReader(f)
    #     for row in reader:
    #         if row['userid'] ==current_user.id:
    #             submissions.append(row)

    submissions = load_all_subs_for_curr_user()

    submissions.sort(key=lambda r:r['timestamp'],reverse=True)

    # avail Probs loaded
    problems = sorted(os.listdir(PROB_DIR))

    # put into janji
    return render_template('index.html',
                            problems=problems, 
                            submissions=submissions)


# the pages for problems
@app.route('/problem/<pid>', methods=['GET', 'POST'])
@login_required
def problem(pid):
    prob_dir = os.path.join(PROB_DIR, pid)
    if not os.path.isdir(prob_dir):
        return "Problem not found, maybe... the problem is YOU", 404


    # prob statement need to be stored in description.txt
    description = ''
    desc_file = os.path.join(prob_dir, 'description.txt')
    if os.path.exists(desc_file):
        description = open(desc_file).read()


    # fetch the code
    message = None
    if request.method =='POST':
        code = request.form.get('code', '').strip()
        if not code:
            message ='write atleast something before submitting, might get partial marks dawg\n'
        else:
            sub_id = uuid.uuid4().hex # rendom ID
            sub_path = os.path.join(SUB_DIR, sub_id)
            os.makedirs(sub_path)

            # save code and metadata in "submissions" folder
            open(os.path.join(sub_path,'main.cpp'),'w').write(code)
            open(os.path.join(sub_path,'status.txt'),'w').write('pending')

            # save in csv for script_runner.py
            timestamp = datetime.now().isoformat(sep=' ',timespec='seconds')
            # with open(CSV_FILE, 'a', newline='') as f:
            #     writer = csv.writer(f)
            #     writer.writerow([sub_id, pid, 'pending', timestamp,current_user.id])
            add_submission(sub_id=sub_id, problem=pid, userid=current_user.id, status='pending', timestamp=timestamp)

            message = f'Submitted! Your submission ID is {sub_id}.'


    return render_template('problem.html', 
                            pid=pid, 
                            description=description,
                            message=message)

@app.route('/status/<sub_id>')
@login_required
def status(sub_id):
    # Find entry in csv
    entry = None
    # with open(CSV_FILE, newline='') as f:
    #     for row in csv.DictReader(f):
    #         if row['id']==sub_id:
    #             entry= row
    #             break
    # if not entry:
    #     return 'Submission ID not found', 404

    try:
        entry = get_submission(sub_id)
    except KeyError:
        return 'Submission ID not found', 404

    # Read result if completed
    result = None

    if entry['status'] == 'accepted' or entry['status'] == 'failed': # isko improve krna hai
        res_file = os.path.join(SUB_DIR, sub_id, 'result.txt')
        if os.path.exists(res_file):
            result = open(res_file).read()
    submitted_code = os.path.join(SUB_DIR, sub_id, 'main.cpp')

    if not os.path.exists(submitted_code):
        delete_submission(sub_id)  # remove from db
        return f'Your submission vanished into thin air lmao. Note your submission ID{sub_id} for debugginf purposes ', 404
    else:
        with open(submitted_code) as f:
            submitted_code = f.read()

    # see if debug status is set to true for this problem
    pid=entry['problem']
    prob_dir =os.path.join(PROB_DIR, pid)
    config_path =os.path.join(prob_dir, 'config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config=json.load(f)
        debug_mode=config.get('DEBUG', False)
    else:
        debug_mode = False
    
    if debug_mode:
        downloads = []
        testcases_path = os.path.join(prob_dir, 'tests')
        if os.path.exists(testcases_path):
            for fname in os.listdir(testcases_path):
                if fname.startswith('input') and fname.endswith('.txt'):
                    downloads.append({
                        'input': fname,
                        'output': fname.replace('input', 'output')
                    })

    # putting in same page was not working out, so made 2 separate pages 
    if debug_mode:
        return render_template('status_debug.html', sub_id=sub_id,
                            pid=pid,
                            status=entry['status'],
                            time=entry['timestamp'],
                            result=result,
                            submitted_code=submitted_code,
                            downloads=downloads,
                            debug_mode=debug_mode)
    else:
        return render_template('status.html', sub_id=sub_id,
                            pid=pid,
                            status=entry['status'],
                            time=entry['timestamp'],
                            result=result,
                            submitted_code=submitted_code,
                            debug_mode=debug_mode)

@app.route('/problems/<pid>/tests/<path:filename>')
@login_required
def serve_testfile(pid, filename):
    # check if file exists
    tests_dir = os.path.join(PROB_DIR, pid, 'tests')
    if not os.path.exists(tests_dir) or not os.path.isdir(tests_dir):
        return "directory not found for the tests bruh", 404
    return send_from_directory(os.path.join(PROB_DIR, pid, 'tests'), filename)


##############################################################################################








################################### USER AUTHENTICATION+LOGIN ###############################


login_manager = LoginManager(app)
login_manager.login_view = "login"  # redirect location

USER_CSV = os.path.join(BASE_DIR, 'users.csv')

# no idea what the below stuff does, but stackflow says so
# seems like it is used by the library for storing user
class User(UserMixin):
    def __init__(self, user_id, username, password_hash):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash

# helper function
def find_user_row(user_id):
    with open(USER_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['user_id'] == user_id:
                return row
    return None

# load user
@login_manager.user_loader
def load_user(user_id):
    row = find_user_row(user_id)
    if row:
        return User(row['user_id'],row['username'],row['password_hash'])
    else:
        return None

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password = request.form["password"]

        # if user exists
        with open(USER_CSV, newline='') as f:
            reader=csv.DictReader(f)
            for row in reader:
                if row['username']==username and check_password_hash(row['password_hash'], password):
                    user = User(row['user_id'],row['username'],row['password_hash'])
                    login_user(user)
                    flash("Login successful!","success")
                    return redirect(url_for("index")) # home page

        flash("Invalid username or password", "danger")
        return redirect(url_for("login"))

    else:        # request.method == "GET"
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        password_hash = generate_password_hash(password)

        # already exists
        with open(USER_CSV, newline='') as f:
            reader=csv.DictReader(f)
            for row in reader:
                if row['username']==username:
                    flash("username taken bruh", "danger")
                    return redirect(url_for("register"))

        # new user
        user_id = str(uuid.uuid4()) # rendom user id
        with open(USER_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([user_id, username, password_hash])

        flash("Registration successful dawg! Now put the same stuff again.", "success")
        return redirect(url_for("login"))

    else:           # request.method =="GET"
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        return render_template("register.html")


#############################################################################################





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)