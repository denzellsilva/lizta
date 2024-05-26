from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import hashlib

app = Flask(__name__)
app.secret_key = 'your_secret_key' # Set a secret key for sessions

# Configure MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="mysql"  # Connect to the default MySQL database
)
cursor = db.cursor()

# Check if the database exists
cursor.execute("SHOW DATABASES LIKE 'to_do_list'")
database_exists = cursor.fetchone()

if not database_exists:
    # Create the database
    cursor.execute("CREATE DATABASE to_do_list")
    db.commit()

# Switch to the created database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="to_do_list"
)
cursor = db.cursor()

# Check if the users table exists
cursor.execute("SHOW TABLES LIKE 'users'")
users_table_exists = cursor.fetchone()

if not users_table_exists:
    # Create the users table with InnoDB engine
    cursor.execute("CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password VARCHAR(100) NOT NULL, date_added TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, date_edited TIMESTAMP on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB")
    db.commit()

# Check if the lists table exists
cursor.execute("SHOW TABLES LIKE 'lists'")
lists_table_exists = cursor.fetchone()

if not lists_table_exists:
    # Create the lists table with InnoDB engine
    cursor.execute("CREATE TABLE lists (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) NOT NULL, list_name VARCHAR(255) NOT NULL, FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE) ENGINE=InnoDB")
    db.commit()

# Check if the tasks table exists
cursor.execute("SHOW TABLES LIKE 'tasks'")
tasks_table_exists = cursor.fetchone()

if not tasks_table_exists:
    # Create the tasks table with InnoDB engine
    cursor.execute("CREATE TABLE tasks (id INT AUTO_INCREMENT PRIMARY KEY, list_id INT NOT NULL, task_name VARCHAR(255) NOT NULL, FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE ON UPDATE CASCADE) ENGINE=InnoDB")
    db.commit()
    
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    else:
        return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    username = request.form['username']
    password = request.form['password']

    # Hash the password for comparison
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user and user[2] == hashed_password:
        session['id'] = user[0]
        session['username'] = username
        return redirect(url_for('dashboard'))
    else:
        error_messages = {'login_error': "Invalid username or password. Please try again."}
        return render_template('index.html', errors=error_messages)

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        # Fetch lists for the logged-in user
        cursor.execute("SELECT * FROM lists WHERE username = %s", (session['username'],))
        lists = cursor.fetchall()
        data = []
        for list_item in lists:
            cursor.execute("SELECT * FROM tasks WHERE list_id = %s", (list_item[0],))
            tasks = cursor.fetchall()
            data.append({'list_id': list_item[0],'list_name': list_item[2], 'tasks': tasks})  # Corrected index for list name
        return render_template('dashboard.html', username=session['username'], data=data)
    else:
        return redirect(url_for('index'))

    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        error_messages = {}

        # Check if passwords match
        if password != confirm_password:
            error_messages['password_match'] = "Passwords do not match."

        # Hash the password before storing it in the database
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Check if username is already taken
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            error_messages['username_taken'] = "Username already exists. Please choose a different one."

        if error_messages:
            return render_template('signup.html', errors=error_messages)
        else:
            # Insert new user into database
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            db.commit()
            success_message = "Account created successfully. You can now login."
            return render_template('signup.html', success=success_message)
    else:
        return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/create_list', methods=['GET', 'POST'])
def create_list():
    if request.method == 'POST':
        list_name = request.form['list_name']
        tasks = request.form.getlist('tasks[]')  # Get all the tasks from the form
        
        # Insert the new list name into the database along with the username
        username = session['username']
        cursor.execute("INSERT INTO lists (username, list_name) VALUES (%s, %s)", (username, list_name))
        db.commit()
        
        # Get the ID of the inserted list
        list_id = cursor.lastrowid
        
        # Insert the tasks into the database
        for task in tasks:
            cursor.execute("INSERT INTO tasks (list_id, task_name) VALUES (%s, %s)", (list_id, task))
            db.commit()
        
        return redirect(url_for('index'))
    else:
        return render_template('create-list.html')

@app.route('/show_list/<int:list_id>')
def show_list(list_id):
    if 'username' in session:
        # Fetch list details based on list_id
        cursor.execute("SELECT * FROM lists WHERE id = %s", (list_id,))
        list_data = cursor.fetchone()
        if list_data:
            # Fetch tasks for the list
            cursor.execute("SELECT * FROM tasks WHERE list_id = %s", (list_id,))
            tasks = cursor.fetchall()
            return render_template('show_list.html', list_name=list_data[2], tasks=tasks, list_id=list_id)
        else:
            return "List not found."
    else:
        return redirect(url_for('index'))

# Add this route to your Flask application
@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    if 'username' in session:
        if request.method == 'POST':
            updated_task = request.form.get('updated_task')

            # Get the list_id associated with the task
            cursor.execute("SELECT list_id FROM tasks WHERE id = %s", (task_id,))
            list_id = cursor.fetchone()[0]

            # Update the task in the database
            cursor.execute("UPDATE tasks SET task_name = %s WHERE id = %s", (updated_task, task_id))
            db.commit()

            # Redirect to the show_list route to display the updated list
            return redirect(url_for('show_list', list_id=list_id))
    else:
        return redirect(url_for('index'))

from flask import jsonify, redirect, url_for

@app.route('/delete_task/<int:task_id>', methods=['GET', 'POST'])
def delete_task(task_id):
    if request.method in ['GET', 'POST']:
        # Ensure the user is logged in
        if 'username' not in session:
            return redirect(url_for('index'))

        # Fetch the task from the database
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()

        if task:
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            db.commit()
            return redirect(url_for('show_list', list_id=task[1]))  # Redirect after successful deletion with list_id
        else:
            return '', 404  # Task not found
    else:
        return '', 405  # Method not allowed response

@app.route('/add_task/<int:list_id>', methods=['GET', 'POST'])
def add_task(list_id):
    if request.method == 'POST':
        # Ensure the user is logged in
        if 'username' not in session:
            return redirect(url_for('index'))

        # Get the task name from the form
        tasks = request.form.getlist('tasks[]')

        # Insert the task into the database
        for task in tasks:
            cursor.execute("INSERT INTO tasks (list_id, task_name) VALUES (%s, %s)", (list_id, task))
            db.commit()
            
        # Redirect back to the show_list route for the current list
        return redirect(url_for('show_list', list_id=list_id))
    else:
        # Fetch list name based on list_id
        cursor.execute("SELECT list_name FROM lists WHERE id = %s", (list_id,))
        list_name = cursor.fetchone()[0]

        cursor.execute("SELECT * FROM lists WHERE id = %s", (list_id,))
        list_data = cursor.fetchone()
        if list_data:
            # Fetch tasks for the list
            cursor.execute("SELECT * FROM tasks WHERE list_id = %s", (list_id,))
            tasks = cursor.fetchall()

        # Render the add_task.html template with list_name
        return render_template('add_task.html', list_id=list_id, list_name=list_name, tasks=tasks)
    
@app.route('/update_list_name/<int:list_id>', methods=['POST'])
def update_list_name(list_id):
    if 'username' in session:
        if request.method == 'POST':
            updated_list_name = request.form.get('updated_list_name')

            # Update the list name in the database
            cursor.execute("UPDATE lists SET list_name = %s WHERE id = %s", (updated_list_name, list_id))
            db.commit()

            # Redirect to the show_list route to display the updated list
            return redirect(url_for('show_list', list_id=list_id))
    else:
        return redirect(url_for('index'))
    
@app.route('/delete_list/<int:list_id>', methods=['GET', 'POST'])
def delete_list(list_id):
    if request.method in ['GET', 'POST']:
        # Ensure the user is logged in
        if 'username' not in session:
            return redirect(url_for('index'))

        # Delete the list from the database
        cursor.execute("DELETE FROM lists WHERE id = %s", (list_id,))
        db.commit()
        
        # Redirect to the dashboard after successful deletion
        return redirect(url_for('dashboard'))
    else:
        return '', 405  # Method not allowed response

if __name__ == "__main__":
    app.run(debug=True)
