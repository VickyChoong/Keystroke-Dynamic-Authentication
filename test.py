import numpy as np
import time
from tensorflow.keras.models import load_model
import msvcrt  # For Windows, use 'msvcrt' to capture keypress timings
import sys
import os
from sklearn.preprocessing import normalize

# Load the trained model
model = load_model('best_neural_network_model_total.h5')

# Verify model loading
print("Model loaded successfully!")
print(f"Model input shape: {model.input_shape}")
print(f"Model summary: \n{model.summary()}")

# Predefined phrase
phrase = "#tie5Roanle"

# Function to capture typing data (H, DD, UD)
def capture_typing_data(phrase):
    typing_data = {'H': [], 'DD': [], 'UD': []}
    keydown_times = []
    keyup_times = []
    
    print(f"Type the phrase: {phrase}")
    input_text = ""
    for i, expected_char in enumerate(phrase):
        keydown_time = time.time()

        # For Windows
        if sys.platform.startswith("win"):
            char = msvcrt.getch().decode()  # Capture key press
        else:
            print("This code is designed for Windows. Please run it on Windows.")
            return None

        if char != expected_char:
            print(f"Expected '{expected_char}', but got '{char}'. Please try again.")
            return None
        
        input_text += char
        keyup_time = time.time()

        # Store the keydown and keyup times
        keydown_times.append(keydown_time)
        keyup_times.append(keyup_time)

        # Calculate hold time for current character (H)
        hold_time = keyup_time - keydown_time
        typing_data['H'].append(hold_time)

        if i > 0:
            # Calculate DD (Keydown-Keydown) and UD (Keyup-Keydown)
            dd_time = keydown_time - keydown_times[i-1]
            ud_time = keydown_time - keyup_times[i-1]
            typing_data['DD'].append(dd_time)
            typing_data['UD'].append(ud_time)

    return typing_data

# Function to convert typing data to input format for the model
def prepare_input_data(typing_data):
    input_data = np.concatenate([typing_data['H'], typing_data['DD'], typing_data['UD']])
    input_data = np.reshape(input_data, (1, -1))
    
    # Normalize the input data as done during model training
    input_data = normalize(input_data)
    
    return input_data

# Function to save the registered typing profile
def save_typing_profile(username, profile):
    os.makedirs('profiles', exist_ok=True)  # Create a 'profiles' directory if it doesn't exist
    np.save(f'profiles/{username}_profile.npy', profile)  # Save the profile as a .npy file

# Function to load the registered typing profile
def load_typing_profile(username):
    profile_path = f'profiles/{username}_profile.npy'
    if os.path.exists(profile_path):
        return np.load(profile_path)
    else:
        return None

# Step 1: Register a new user with 8 typing samples
def register_user(username):
    print("Registration phase: Type the predefined phrase 8 times to register your typing pattern.")
    stored_typing_samples = []

    for attempt in range(8):
        print(f"\nAttempt {attempt + 1}:")
        typing_data = capture_typing_data(phrase)
        
        if typing_data is not None:
            stored_typing_samples.append(prepare_input_data(typing_data))
        else:
            attempt -= 1  # Retry if the phrase was typed incorrectly

    # Calculate average profile
    stored_typing_samples = np.array(stored_typing_samples)
    average_typing_profile = np.mean(stored_typing_samples, axis=0)
    print(f"Average typing profile calculated. Shape: {average_typing_profile.shape}")
    
    # Save the average profile for the user
    save_typing_profile(username, average_typing_profile)
    print(f"Typing profile saved for user: {username}")

# Step 2: Authenticate the user by comparing current typing pattern with registered profile
def authenticate_user(username):
    # Load the user's registered typing profile
    registered_typing_profile = load_typing_profile(username)
    
    if registered_typing_profile is None:
        print(f"No registered typing profile found for user: {username}")
        return
    
    # Ask the user to type the phrase again for authentication
    print("\nAuthentication phase: Type the predefined phrase again.")
    current_typing_data = capture_typing_data(phrase)

    if current_typing_data is not None:
        current_input_data = prepare_input_data(current_typing_data)
        print(f"Current input data shape: {current_input_data.shape}")

        # Step 3: Get predictions from the model
        registered_prediction = model.predict(registered_typing_profile)
        current_prediction = model.predict(current_input_data)

        # Step 4: Compare model's output
        # Here, we use the probability or class output directly, without calculating distances
        print(f"Registered prediction: {registered_prediction}")
        print(f"Current prediction: {current_prediction}")
        
        threshold = 0.85  # Set a threshold for matching (can adjust this based on testing)
        match_probability = np.max(current_prediction)  # Use max probability for authentication

        # Output the result
        if match_probability >= threshold:
            print(f"Authentication successful. Match probability: {match_probability:.2f}")
        else:
            print(f"Authentication failed. Match probability: {match_probability:.2f}")
    else:
        print("Failed to capture current typing data.")

# Main flow: Register or authenticate a user
def main():
    choice = input("Do you want to (1) register a new user or (2) authenticate an existing user? Enter 1 or 2: ")

    if choice == '1':
        username = input("Enter a username to register: ")
        register_user(username)
    elif choice == '2':
        username = input("Enter a username to authenticate: ")
        authenticate_user(username)
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
