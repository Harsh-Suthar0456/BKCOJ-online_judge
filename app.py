import os
import uuid
import csv
from datetime import datetime
import json
from flask import Flask, render_template, request, url_for, send_from_directory

app =Flask(__name__)
BASE_DIR =os.path.abspath(os.path.dirname(__file__))
SUB_DIR =os.path.join(BASE_DIR, 'submissions')
CSV_FILE =os.path.join(BASE_DIR, 'submissions.csv')
PROB_DIR =os.path.join(BASE_DIR, 'problems')

# Set up subs
os.makedirs(SUB_DIR, exist_ok=True) # leave if exists

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE,'w',newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id','problem','status','timestamp'])

# the home page stuff
@app.route('/')
def index():
    # Previous subs loaded
    submissions = []
    with open(CSV_FILE, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            submissions.append(row)

    submissions.sort(key=lambda r: r['timestamp'], reverse=True)

    # avail Probs loaded
    problems = sorted(os.listdir(PROB_DIR))

    # put into janji
    return render_template('index.html',
                            problems=problems, 
                            submissions=submissions)


# the pages for problems
@app.route('/problem/<pid>', methods=['GET', 'POST'])
def problem(pid):
    prob_dir = os.path.join(PROB_DIR, pid)
    if not os.path.isdir(prob_dir):
        return "Problem not found", 404


    # prob statement need to be stored in description.txt
    description = ''
    desc_file = os.path.join(prob_dir, 'description.txt')
    if os.path.exists(desc_file):
        description = open(desc_file).read()

    # fetch the code
    message = None
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            message = 'Error: No code submitted.'
        else:
            sub_id = uuid.uuid4().hex
            sub_path = os.path.join(SUB_DIR, sub_id)
            os.makedirs(sub_path)

            # Save code and metadata in "submissions" folder
            open(os.path.join(sub_path,'main.cpp'),'w').write(code)
            open(os.path.join(sub_path,'status.txt'),'w').write('pending')

            # save in csv for script_runner.py
            timestamp = datetime.now().isoformat(sep=' ',timespec='seconds')
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([sub_id, pid, 'pending', timestamp])

            message = f'Submitted! Your submission ID is {sub_id}.'

    return render_template('problem.html', 
                            pid=pid, 
                            description=description,
                            message=message)

@app.route('/status/<sub_id>')
def status(sub_id):
    # Find entry in csv
    entry = None
    with open(CSV_FILE, newline='') as f:
        for row in csv.DictReader(f):
            if row['id'] == sub_id:
                entry = row
                break
    if not entry:
        return 'Submission ID not found', 404

    # Read result if completed
    result = None

    if entry['status'] == 'accepted' or entry['status'] == 'failed': # isko improve krna hai
        res_file = os.path.join(SUB_DIR, sub_id, 'result.txt')
        if os.path.exists(res_file):
            result = open(res_file).read()
    submitted_code = os.path.join(SUB_DIR, sub_id, 'main.cpp')

    if not os.path.exists(submitted_code):
        return 'Submission code not found', 404
    else:
        with open(submitted_code) as f:
            submitted_code = f.read()

    # see if debug status is set to true for this problem
    pid = entry['problem']
    prob_dir = os.path.join(PROB_DIR, pid)
    config_path = os.path.join(prob_dir, 'config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        debug_mode = config.get('DEBUG', False)
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
def serve_testfile(pid, filename):
    # check if file exists
    tests_dir = os.path.join(PROB_DIR, pid, 'tests')
    if not os.path.exists(tests_dir) or not os.path.isdir(tests_dir):
        return "Tests directory not found", 404
    return send_from_directory(os.path.join(PROB_DIR, pid, 'tests'), filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)