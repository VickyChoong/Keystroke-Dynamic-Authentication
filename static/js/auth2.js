document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('email').value = '';
    document.getElementById('username').value = '';
    document.getElementById('typing_input').value = '';
});

let currentAttempt = 1;
let typingData = [];  // Array to store the H, DD, UD for 3 attempts
let lastKeydownTime = null;
let lastKeyupTime = null;
let tempData = {
    H: [],  // Hold times
    DD: [],  // Keydown-Keydown times
    UD: []  // Keyup-Keydown times
};

// Function to check if email and username exist and match
function checkEmailAndUsername() {
    const email = document.getElementById('email').value;
    const username = document.getElementById('username').value;

    // Check if both fields are filled
    if (!email || !username) {
        document.getElementById('error_message').innerText = "Please fill in both email and username!";
        return;
    }

    fetch('/check_email_username', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email: email, username: username })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('error_message').innerText = data.error;
        } else {
            nextStep(2);  // Proceed to password step
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('error_message').innerText = "An error occurred. Please try again.";
    });
}

// Function to move to the next step in the form
function nextStep(stepNumber) {
    document.querySelectorAll('.step').forEach(step => {
        step.style.display = 'none';  // Hide all steps
    });
    document.getElementById('step' + stepNumber).style.display = 'block';  // Show the current step
}

// Listen for keydown and keyup events on the typing input field to capture typing pattern
document.getElementById('typing_input').addEventListener('keydown', function(event) {
    const currentTime = performance.now() / 1000;  // Convert milliseconds to seconds
    if (tempData.H.length < 11) {
        if (lastKeydownTime !== null) {
            const holdTime = currentTime - lastKeydownTime;
            tempData.H.push(holdTime);  // Push hold time in seconds
        }
        lastKeydownTime = currentTime;
    }
});

document.getElementById('typing_input').addEventListener('keyup', function(event) {
    const currentTime = performance.now() / 1000;  // Convert milliseconds to seconds
    if (tempData.UD.length < 11) {
        if (lastKeyupTime !== null) {
            const udTime = currentTime - lastKeyupTime;
            tempData.UD.push(udTime);  // Push UD time in seconds
        }
        lastKeyupTime = currentTime;
    }
    if (tempData.DD.length < 11) {
        const ddTime = currentTime - lastKeydownTime;
        tempData.DD.push(ddTime);  // Push DD time in seconds
    }
    lastKeyupTime = currentTime;
});

// Function to handle typing attempts and collect data
function authenticateAttempt() {
    const inputElement = document.getElementById('typing_input');
    const inputValue = inputElement.value.trim();

    if (!inputValue) {
        alert('Password cannot be empty! Please enter your password.');
        return;
    }

    // Concatenate H, DD, and UD into a single array
    let concatenatedData = [...tempData.H, ...tempData.DD, ...tempData.UD];

    // Check if the total number of features is fewer than 31, pad if necessary
    if (concatenatedData.length < 31) {
        concatenatedData = concatenatedData.concat(new Array(31 - concatenatedData.length).fill(0));
    }

    // Store the current attempt as a dictionary of H, DD, and UD
    typingData.push({
        H: [...tempData.H],
        DD: [...tempData.DD],
        UD: [...tempData.UD]
    });

    tempData = { H: [], DD: [], UD: [] };  // Reset tempData
    inputElement.value = '';  // Clear the input

    if (currentAttempt < 3) {
        currentAttempt++;
        document.getElementById('attempt_message').textContent = `Please type your password in the box below (Attempt ${currentAttempt} of 3)`;
    } else {
        submitTypingData(inputValue);  // Submit typing data after 3 attempts, passing the password
    }
}

// Submit typing data to the server for authentication
function submitTypingData(password) {
    const email = document.getElementById('email').value;
    const username = document.getElementById('username').value;

    const payload = {
        email: email,
        username: username,
        password: password,  // Send password for validation
        typing_sessions: typingData  // Send the 3 typing attempts for authentication
    };

    fetch('/authenticate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
            window.location.href = data.redirect_url;
        } else {
            alert(data.message);
            window.location.href = data.redirect_url;
        }
    })
    .catch(error => {
        console.error('Error during authentication:', error);
        alert('An error occurred during authentication. Please try again.');
    });
}
