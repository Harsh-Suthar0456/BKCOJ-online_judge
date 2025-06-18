# Online Judge Project

## Overview
BKCOJ is a Flask based Online Judge, supporting user-authentication, code submission, and scalable asynchronous submission handler.

## Installation

1. Clone the repo
```bash
git clone https://github.com/Harsh-Suthar0456/online_judge.git
cd online_judge
```
2. Install dependencies
```bash
pip install -r requirements.txt
```
3. Make a Docker image, this will be used by ```script_runner.py``` for secure code execution
```bash
docker build -t code-runner:latest .
```
4. Run the Flask app
```bash
python3 app.py
```
5. On a separate terminal, run `script_runner.py`
```bash
python3 script_runner.py
```
6. Open your browser and go to `http://localhost:5000`, this should land you to the login page. You can use the default credentials:
   - Username: `dos`
   - Password: `dos456`

    or you can register a new user

## Project Structure
```perl
online_judge
├── Basic_checks/        
├── problems/        
│   ├── <problem_id>
│   │   ├── description.txt
│   │   ├── config.json   
|   |   └── tests
│   │       ├── input1.txt
│   │       └── output1.txt
├── static/              
├── templates/           
├── submissions/  
│   ├── <submission_id>/
│   │   ├── main.cpp
│   │   ├── result.txt
│   │   └── status.txt
├── users.csv             
├── submissions.db        
├── app.py               
├── script_runner.py      
├── dockerfile            
├── requirements.txt      
└── README.md            
```

## User Guide
1. **Login**: Use the default credentials or register a new user.
2. **Home Page**: You can navigate through available problems and view your previous submissions. Would extend it later to have a profile page too.
3. **Submit Code**: Select a problem, write your code in the provided editor, and submit it. The code will be executed in a secure Docker container. You will recieve a submission ID to track your submission status.
4. **View Submissions**: You can view the status of your submissions, including whether they passed or failed the test cases. If the debug mode is enabled, you can also see the hidden test cases and expected output for each problem.
5. **Logout**: You can log out from the application from the navigation bar.

## Problem setting guide
You can create a new problem by simply make a directory in the `problems` directory with the following structure:
```perl
problems/
    └── problem_name/
        ├── description.txt
        ├── configs.json
        ├── tests
        │   ├── input1.txt
        │   ├── input2.txt
        │   ├── output1.txt
        │   └── output2.txt
```
- Supports any number of test cases, just make sure to have the input and output files named correctly (e.g., `input1.txt`, `output1.txt`, etc.). Currently supports only token matching based test cases, would later extend it to support more complex test cases.
- The `description.txt` file should contain the problem statement. Would later change it to rather support a markdown file.
- `configs.json` should contain the problem configurations like `TIME_LIMIT`, `MEMORY_LIMIT`, and `DEBUG`.

## Features
1. ### User authentication and Isolation
    - Uses flask-login for user authentication framework, along with werkzeug for password hashing
    - userid, username, and password are stored in user.csv
    - `Current_user` can only access their own submissions
2. ### Asynchronous code submission
    - Uses a separate process to handle code submissions in the backend, allowing the main Flask app to remain responsive
    - Code is executed in a Docker container for security. Although I believe there are still some vulnerabilities regarding file permissions, would work on them later
3. ### SQLlite database for submissions
    - Earlier implementation for submissions was using a CSV file, but is switch to SQLlite for better performance and scalability.
4. ### Debug mode for problems
    - A debug mode is available(can be toggled in the `configs.json` file) which allows users to see the hidden testcases and expected output for a problem
5. ### Jinja2 templating engine
    - Uses Jinja2 templating engine for rendering HTML templates, allowing for dynamic content generation, which is used for the home page, problem page, and submission status page, extending on `base.html` for common layout

## Future Work
1. **Profile Page**: Add a profile page for users to view their submissions and statistics.
2. **Problem Editor**: Implement a problem editor for admins to create and manage problems directly from the web interface.
3. **Markdown Support**: Change the problem description to support markdown files for better formatting.
4. **Better Code Editor**: Integrate a better code editor with syntax highlighting and auto-identation.
5. **More secure code execution**: Improve the security of code execution.

