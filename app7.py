from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
import json
import numpy as np
import joblib
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from datetime import datetime
import pytz
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize global variables for model and scaler
knn_model = None
scaler = None

# Load model and scaler
def load_model():
    global knn_model, scaler
    if os.path.exists('knn_model.pkl') and os.path.exists('scaler_knn.pkl'):
        knn_model = joblib.load('knn_model.pkl')
        scaler = joblib.load('scaler_knn.pkl')

load_model()  # Load the model at startup

# Function to connect to the MySQL database
def db_connect():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        passwd='',
        database='projectfyp'
    )

# Main route for landing page and authentication (Sign In/Sign Up)
@app.route('/')
def index():
    return render_template('index4.html')

# Route to render the enrollment form (Sign Up)
@app.route('/enroll')
def enroll():
    return render_template('enroll4.html')

@app.route('/check_email_username', methods=['POST'])
def check_email_username():
    data = request.json
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({'error': 'Both email and username are required!'}), 400

    # Connect to the database
    db = db_connect()
    cursor = db.cursor()

    # Check if email and username match in the database
    cursor.execute("SELECT * FROM users WHERE email = %s AND username = %s", (email, username))
    user = cursor.fetchone()

    cursor.close()
    db.close()

    if user:
        print(f'User found for email: {email}, username: {username}')  # Debugging log
        return jsonify({'message': 'Email and username matched!'}), 200
    else:
        print(f'No user found for email: {email}, username: {username}')  # Debugging log
        return jsonify({'error': 'Email or username is incorrect!'}), 404
    
# Route to handle each password attempt
@app.route('/check_password_attempt', methods=['POST'])
def check_password_attempt():
    data = request.json
    email = data['email']
    username = data['username']
    password = data['password']

    db = db_connect()
    cursor = db.cursor()
    cursor.execute("SELECT id, password FROM users WHERE email = %s AND username = %s", (email, username))
    user = cursor.fetchone()
    cursor.close()
    db.close()

    if user:
        user_id, stored_password = user
        if stored_password == password:
            return jsonify({'status': 'success', 'message': 'Password is correct.'}), 200
        else:
            return jsonify({'status': 'failed', 'message': 'Incorrect password. Please try again.'}), 401
    else:
        return jsonify({'status': 'failed', 'message': 'User not found.'}), 404

# Enrollment route to handle user data and typing patterns
@app.route('/enroll_user', methods=['POST'])
def enroll_user():
    data = request.json
    email = data['email']
    username = data['username']
    password = data['password']
    typing_sessions = data['typing_sessions']  # Expecting a list of dicts with keys 'H', 'DD', 'UD'

    # Validate typing sessions structure
    for session in typing_sessions:
        if 'H' not in session or 'DD' not in session or 'UD' not in session:
            return jsonify({'error': 'Missing keys in typing session data. Each session must have H, DD, and UD.'}), 400

    # Connect to the database
    db = db_connect()
    cursor = db.cursor()

    try:
        # Insert user details into the users table
        cursor.execute("INSERT INTO users (email, username, password) VALUES (%s, %s, %s)", (email, username, password))
        user_id = cursor.lastrowid

        # Insert typing data into keystroke_data table
        for session_index, session_data in enumerate(typing_sessions):
            H = json.dumps(session_data['H'])  # Convert to JSON for storage
            DD = json.dumps(session_data['DD'])
            UD = json.dumps(session_data['UD'])

            cursor.execute(
                "INSERT INTO keystroke_data (user_id, session_index, H, DD, UD) VALUES (%s, %s, %s, %s, %s)",
                (user_id, session_index, H, DD, UD)
            )
        
        # Commit the changes
        db.commit()

        # Trigger model re-training after user enrollment
        retrain_model()
        load_model()
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()

    return jsonify({
        'message': 'User enrolled successfully!',
        'redirect_url': url_for('index')
    }), 200

# Authentication API (Step 2 during Sign In)
@app.route('/authenticate', methods=['POST'])
def authenticate_user():
    data = request.json
    email = data['email']
    username = data['username']
    password = data['password']
    typing_sessions = data['typing_sessions']  # H, DD, UD from the 3 typing attempts

    # Connect to the database
    db = db_connect()
    cursor = db.cursor()

    # Check if the user exists
    cursor.execute("SELECT id, password FROM users WHERE email = %s AND username = %s", (email, username))
    user = cursor.fetchone()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_id, stored_password = user

    # Password check
    if stored_password != password:
        return jsonify({'error': 'Incorrect password. Please try again.'}), 401  # Stop further processing
    
    # Set session for user
    session['user_id'] = user_id
    session['username'] = username  # Store the username in the session

    # Reload the model to ensure it’s up-to-date
    load_model()

    attempt_percentages = []  # To store match percentages for each attempt

    # Fetch user's stored keystroke profile
    cursor.execute("SELECT H, DD, UD FROM keystroke_data WHERE user_id = %s", (user_id,))
    keystroke_data = cursor.fetchall()

    if not keystroke_data:
        return jsonify({'error': 'No typing data found for user'}), 404

    overall_match_count = 0
    highest_match_percentage = 0  # Track the highest match probability across all attempts

    # Loop through the 3 sign-in attempts
    for attempt_index, attempt in enumerate(typing_sessions):
        print(f"\nSign-in Attempt {attempt_index + 1}:")
        match_count = 0
        attempt_highest_percentage = 0  # Track the highest probability for this specific attempt

        for session_index, row in enumerate(keystroke_data):
            stored_H = json.loads(row[0])
            stored_DD = json.loads(row[1])
            stored_UD = json.loads(row[2])

            # Prepare the input data for comparison
            input_data = np.concatenate([attempt['H'], attempt['DD'], attempt['UD']])

            # Pad input_data to 33 features (since the scaler expects 33 features)
            if len(input_data) < 33:
                input_data = np.pad(input_data, (0, 33 - len(input_data)), 'constant')

            # Scale the input data
            input_data_scaled = scaler.transform([input_data])

            # Get the prediction
            probabilities = knn_model.predict_proba(input_data_scaled)
            user_probability = probabilities[0][user_id - 1] * 100
            attempt_highest_percentage = max(attempt_highest_percentage, user_probability)

            print(f"User ID: {user_id}, Stored Session {session_index + 1}, Match Probability: {user_probability:.2f}%")

            if user_probability >= 60:
                match_count += 1

        # Save the match percentage for this attempt
        attempt_percentages.append(attempt_highest_percentage)

        # Update the highest match probability across all attempts
        highest_match_percentage = max(highest_match_percentage, attempt_highest_percentage)

        # Update overall match count if this attempt is successful
        if match_count >= 3:
            overall_match_count += 1

        print(f"Sign-in Attempt {attempt_index + 1} had {match_count} matches out of 5.")

    # Store attempt percentages in session to retrieve on profile page
    session['attempt_percentages'] = attempt_percentages

    # Determine overall success based on attempts
    successful_login = overall_match_count >= 1

    # Record the highest match percentage for this sign-in session
    cursor.execute(
        "INSERT INTO login_attempts (user_id, success, match_percentage) VALUES (%s, %s, %s)",
        (user_id, successful_login, highest_match_percentage)
    )

    # Commit all attempts to the database
    db.commit()
    cursor.close()
    db.close()

    if overall_match_count >= 1:
        return jsonify({
            'status': 'success',
            'message': f'Authentication successful! {overall_match_count} out of 3 attempts matched.',
            'redirect_url': url_for('profile')
        })
    else:
        return jsonify({
            'status': 'failed',
            'message': f'Authentication failed! {overall_match_count} out of 3 attempts matched.',
            'redirect_url': url_for('index')
        })

@app.route('/profile')
def profile():
    if 'username' in session:
        username = session['username']
        return render_template('profile2.html', username=username)
    else:
        return redirect(url_for('index'))
    
@app.route('/get_keystroke_data', methods=['GET'])
def get_keystroke_data():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 403

    user_id = session['user_id']

    db = db_connect()
    cursor = db.cursor()

    # Retrieve keystroke data for the user
    cursor.execute("SELECT H, DD, UD FROM keystroke_data WHERE user_id = %s", (user_id,))
    keystroke_data = cursor.fetchall()
    cursor.close()
    db.close()

    if not keystroke_data:
        return jsonify({'error': 'No typing data found for user'}), 404

    # Process data into the required format
    H_data = []
    DD_data = []
    UD_data = []

    for row in keystroke_data:
        H_data.append(json.loads(row[0]))  # Hold time data for each session
        DD_data.append(json.loads(row[1])) # Keydown-Keydown time data for each session
        UD_data.append(json.loads(row[2])) # Keyup-Keydown time data for each session

    # Return data in structured format
    return jsonify({
        "H": H_data,
        "DD": DD_data,
        "UD": UD_data
    })

# Convert the datetime to your desired timezone (e.g., Asia/Kuala_Lumpur)
def convert_to_timezone(dt, timezone="Asia/Kuala_Lumpur"):
    if dt is None:
        return None
    utc_dt = dt.replace(tzinfo=pytz.UTC)  # Ensure UTC awareness
    target_tz = pytz.timezone(timezone)
    return utc_dt.astimezone(target_tz).strftime("%Y-%m-%d %H:%M:%S")

# Update `get_last_login_info` with timezone conversion
@app.route('/get_last_login_info', methods=['GET'])
def get_last_login_info():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 403

    user_id = session['user_id']
    db = db_connect()
    cursor = db.cursor()

    # Retrieve last successful login in UTC
    cursor.execute("""
        SELECT login_time, match_percentage 
        FROM login_attempts 
        WHERE user_id = %s AND success = TRUE 
        ORDER BY login_time DESC LIMIT 1
    """, (user_id,))
    last_successful = cursor.fetchone()

    # Retrieve last failed login in UTC
    cursor.execute("""
        SELECT login_time 
        FROM login_attempts 
        WHERE user_id = %s AND success = FALSE 
        ORDER BY login_time DESC LIMIT 1
    """, (user_id,))
    last_failed = cursor.fetchone()

    cursor.close()
    db.close()

    return jsonify({
        'last_successful': {
            'time': last_successful[0].isoformat() if last_successful else None,
            'match_percentage': last_successful[1] if last_successful else None
        },
        'last_failed': last_failed[0].isoformat() if last_failed else None
    })

@app.route('/get_attempt_percentages', methods=['GET'])
def get_attempt_percentages():
    if 'attempt_percentages' in session:
        return jsonify({'attempt_percentages': session['attempt_percentages']})
    else:
        return jsonify({'error': 'No attempt percentages found'}), 404

# Update username route
@app.route('/update_username', methods=['POST'])
def update_username():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 403

    user_id = session['user_id']
    new_username = request.json.get('new_username')

    db = db_connect()
    cursor = db.cursor()

    try:
        cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, user_id))
        db.commit()
        session['username'] = new_username
        return jsonify({'status': 'success', 'message': 'Username updated successfully!'})
    except Exception as e:
        db.rollback()
        return jsonify({'status': 'failed', 'error': str(e)})
    finally:
        cursor.close()
        db.close()

@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.json
    new_password = data['password']
    typing_sessions = data['typing_sessions']
    
    if 'user_id' in session:
        db = db_connect()
        cursor = db.cursor()
        
        # Update password in the users table
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, session['user_id']))

        # Clear existing keystroke data for the user
        cursor.execute("DELETE FROM keystroke_data WHERE user_id = %s", (session['user_id'],))

        # Insert new keystroke data for each session
        for index, session_data in enumerate(typing_sessions):
            H, DD, UD = json.dumps(session_data['H']), json.dumps(session_data['DD']), json.dumps(session_data['UD'])
            cursor.execute("INSERT INTO keystroke_data (user_id, session_index, H, DD, UD) VALUES (%s, %s, %s, %s, %s)", 
                           (session['user_id'], index, H, DD, UD))
        
        db.commit()
        cursor.close()
        db.close()
        
        # Re-train model after updating keystroke data
        retrain_model()
        
        return jsonify({'success': True, 'message': 'Password and keystroke profile updated successfully!'})
    else:
        return jsonify({'error': 'User not logged in'}), 403

@app.route('/get_current_password', methods=['GET'])
def get_current_password():
    if 'user_id' in session:
        db = db_connect()
        cursor = db.cursor()
        
        # Retrieve the current password for the logged-in user
        cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
        result = cursor.fetchone()
        
        cursor.close()
        db.close()
        
        if result:
            # Return the password to be displayed for reference
            return jsonify({'success': True, 'password': result[0]})
        else:
            return jsonify({'success': False, 'error': 'Password not found.'}), 404
    else:
        return jsonify({'success': False, 'error': 'User not logged in.'}), 403 
    
@app.route('/update_typing_profile', methods=['POST'])
def update_typing_profile():
    data = request.json
    typing_sessions = data['typing_sessions']

    if 'user_id' in session:
        db = db_connect()
        cursor = db.cursor()

        # Clear existing keystroke data for the user
        cursor.execute("DELETE FROM keystroke_data WHERE user_id = %s", (session['user_id'],))

        # Insert new keystroke data with consistent padding and length check
        for index, session_data in enumerate(typing_sessions):
            H, DD, UD = json.dumps(session_data['H']), json.dumps(session_data['DD']), json.dumps(session_data['UD'])
            cursor.execute(
                "INSERT INTO keystroke_data (user_id, session_index, H, DD, UD) VALUES (%s, %s, %s, %s, %s)",
                (session['user_id'], index, H, DD, UD)
            )

        db.commit()
        cursor.close()
        db.close()
        
        retrain_model()  # Retrain model to reflect updated typing profile

        return jsonify({'success': True, 'message': 'Keystroke profile updated successfully!'})
    else:
        return jsonify({'error': 'User not logged in'}), 403

# Function to re-train the KNN model
def retrain_model():
    db = db_connect()
    cursor = db.cursor()

    # Fetch all keystroke data from the database
    cursor.execute("SELECT H, DD, UD, user_id FROM keystroke_data")
    all_data = cursor.fetchall()

    # Prepare X and y for re-training
    X = []
    y = []
    for row in all_data:
        H = json.loads(row[0])
        DD = json.loads(row[1])
        UD = json.loads(row[2])
        user_id = row[3]

        input_data = np.concatenate([H, DD, UD])
        if len(input_data) < 33:
            input_data = np.pad(input_data, (0, 33 - len(input_data)), 'constant')

        X.append(input_data)
        y.append(user_id)

    ## Scale the data
    global scaler, knn_model
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Re-train the KNN model
    knn_model_new = KNeighborsClassifier(n_neighbors=5, metric='euclidean')
    knn_model_new.fit(X_scaled, y)

    # Save the updated model and scaler
    joblib.dump(knn_model_new, 'knn_model.pkl')
    joblib.dump(scaler, 'scaler_knn.pkl')

    cursor.close()
    db.close()

def load_model():
    global knn_model, scaler
    knn_model = joblib.load('knn_model.pkl')
    scaler = joblib.load('scaler_knn.pkl')

if __name__ == '__main__':
    app.run(debug=True)
