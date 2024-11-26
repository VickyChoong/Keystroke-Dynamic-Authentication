document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('email').value = '';
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    document.getElementById('typing_input').value = '';
});

// Function to validate password requirements
function validatePassword() {
    const password = document.getElementById('password').value;
    const passwordError = document.getElementById('password-error');
    
    // Regular expression for validation: 8-11 characters, includes uppercase, lowercase, number, and symbol
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,11}$/;

    if (!passwordRegex.test(password)) {
        // Show error message if the password doesn't meet requirements
        passwordError.style.display = 'block';
    } else {
        // Hide error message and proceed to the next step if valid
        passwordError.style.display = 'none';
        nextStep(3);
    }
}


// Function to handle moving to the next step in the form
function nextStep(stepNumber) {
    document.querySelectorAll('.step').forEach(step => {
        step.style.display = 'none';  // Hide all steps
    });

    if (stepNumber === 3) {
        // Display the created password for reference
        const password = document.getElementById('password').value;
        document.getElementById('show_password').textContent = password;  // Display password for reference
    }

    document.getElementById('step' + stepNumber).style.display = 'block';  // Show the current step
}

// Typing data storage and process
let typingData = [];  // Array to store H, DD, UD timings for 5 attempts
let currentAttempt = 1;
let lastKeydownTime = null;
let lastKeyupTime = null;
let tempData = {
    H: [],  // Hold times
    DD: [],  // Keydown-Keydown times
    UD: []  // Keyup-Keydown times
};

// Listen for keydown and keyup events on the typing input field
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

// Function to record typing and validate the password
function recordTyping() {
    const inputElement = document.getElementById('typing_input');
    const inputValue = inputElement.value.trim();
    const password = document.getElementById('password').value;

    if (inputValue !== password) {
        alert('Password does not match. Please retry.');
        inputElement.value = '';  // Clear the input
        return;
    }

    if (inputValue.length > 11) {
        alert('Invalid password, not more than 11 characters. Please retry.');
        inputElement.value = '';  // Clear the input
        return;
    }

    // Ensure H, DD, UD are captured and not empty
    if (tempData.H.length < 1 || tempData.DD.length < 1 || tempData.UD.length < 1) {
        alert('Incomplete typing data. Please retry.');
        return;
    }

    // Define the expected length (e.g., 11, or whatever the required length is)
    const expectedLength = 11;

    // Pad H, DD, and UD arrays to the expected length
    let H_padded = [...tempData.H];
    let DD_padded = [...tempData.DD];
    let UD_padded = [...tempData.UD];

    // Pad H, DD, and UD arrays if they are shorter than expected
    while (H_padded.length < expectedLength) H_padded.push(0);
    while (DD_padded.length < expectedLength) DD_padded.push(0);
    while (UD_padded.length < expectedLength) UD_padded.push(0);

    // Concatenate the padded H, DD, and UD arrays into a single array
    let concatenatedData = [...H_padded, ...DD_padded, ...UD_padded];

    // Store the current attempt as a dictionary of H, DD, and UD
    typingData.push({
        H: H_padded,
        DD: DD_padded,
        UD: UD_padded
    });

    tempData = { H: [], DD: [], UD: [] };  // Reset tempData
    inputElement.value = '';  // Clear the input

    if (currentAttempt < 5) {
        currentAttempt++;
        document.querySelector('#step3 h3').textContent = `Please type your password in the box below (Attempt ${currentAttempt} of 5)`;
    } else {
        submitData();  // All attempts completed, submit data
    }
}


// Function to submit data after 5 attempts
function submitData() {
    const email = document.getElementById('email').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const payload = {
        email: email,
        username: username,
        password: password,
        typing_sessions: typingData  // Send 5 typing sessions with H, DD, UD as separate keys
    };

    fetch('/enroll_user', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message === "User enrolled successfully!") {
            // Show the success message
            document.getElementById('step3').style.display = 'none';
            document.getElementById('enrollment_success').style.display = 'block';

            // Redirect to the landing page after 2 seconds
            setTimeout(() => {
                window.location.href = data.redirect_url;
            }, 2000);
        } else {
            alert(data.error);
        }
    })
    .catch(error => console.error('Error:', error));
}
