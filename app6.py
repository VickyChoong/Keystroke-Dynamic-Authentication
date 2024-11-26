from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
import json
import numpy as np
import joblib
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import Dense, Dropout
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
import pandas as pd

app = Flask(__name__)

# Load the trained model and scaler
model = load_model('best_neural_network_model_total.h5')
scaler = joblib.load('scaler.pkl')

# Function to connect to the MySQL database
def db_connect():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        passwd='',
        database='fyp'
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

# Enrollment route to handle user data and typing patterns
@app.route('/enroll_user', methods=['POST'])
def enroll_user():
    global model, scaler  # Update the global model and scaler after retraining

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
        model, scaler = retrain_model()  # Update the global model and scaler
        
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

    # Fetch user's stored keystroke profile
    cursor.execute("SELECT H, DD, UD FROM keystroke_data WHERE user_id = %s", (user_id,))
    keystroke_data = cursor.fetchall()

    if not keystroke_data:
        return jsonify({'error': 'No typing data found for user'}), 404

    overall_match_count = 0

    # Loop through the 3 sign-in attempts
    for attempt_index, attempt in enumerate(typing_sessions):
        print(f"\nSign-in Attempt {attempt_index + 1}:")
        match_count = 0

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
            probabilities = model.predict(input_data_scaled)
            user_probability = probabilities[0][user_id - 1] * 100

            print(f"User ID: {user_id}, Stored Session {session_index + 1}, Match Probability: {user_probability:.2f}%")

            if user_probability >= 80:
                match_count += 1

        if match_count >= 3:
            overall_match_count += 1

        print(f"Sign-in Attempt {attempt_index + 1} had {match_count} matches out of 5.")

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

# Profile page after successful login
@app.route('/profile')
def profile():
    return render_template('profile.html')

# Function to retrain the CNN model
def retrain_model():
    # Connect to database and fetch all user data
    db = db_connect()
    cursor = db.cursor()

    # Fetch keystroke data for all users
    cursor.execute("SELECT user_id, H, DD, UD FROM keystroke_data")
    data = cursor.fetchall()
    
    if not data:
        return model, scaler  # No data to retrain on

    # Prepare data for training
    X = []
    y = []
    for row in data:
        user_id = row[0]
        H = json.loads(row[1])
        DD = json.loads(row[2])
        UD = json.loads(row[3])

        # Concatenate H, DD, and UD
        X.append(H + DD + UD)
        y.append(user_id - 1)  # User ID is 1-based, so we subtract 1

    # Convert to numpy arrays
    X = np.array(X)
    y = np.array(y)

    # One-hot encode the target labels
    y_one_hot = to_categorical(y)

    # Split the data into training and testing sets with stratification
    X_train, X_test, Y_train, Y_test = train_test_split(X, y_one_hot, test_size=0.2, random_state=1, stratify=y)

    # Standardize the features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Save the scaler for later use
    joblib.dump(scaler, 'scaler.pkl')

    # Define the CNN model
    def cnn_model(input_dim, output_dim, nodes=100, dropout_rate=0.2):
        model = Sequential()
        model.add(Dense(nodes, input_dim=input_dim, activation='relu'))
        model.add(Dropout(dropout_rate))
        model.add(Dense(nodes, activation='relu'))
        model.add(Dropout(dropout_rate))
        model.add(Dense(output_dim, activation='softmax'))
        model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
        return model

    # Initialize and retrain the model
    model = cnn_model(input_dim=X_train_scaled.shape[1], output_dim=y_one_hot.shape[1])
    model.fit(X_train_scaled, Y_train, epochs=100, batch_size=5, validation_data=(X_test_scaled, Y_test))

    # Save the updated model
    model.save('best_neural_network_model_total.h5')

    return model, scaler  # Return the updated model and scaler

if __name__ == '__main__':
    app.run(debug=True)

