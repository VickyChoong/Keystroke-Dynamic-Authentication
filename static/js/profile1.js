document.addEventListener('DOMContentLoaded', function () {
    // Elements for username change
    const updateUsernameBtn = document.getElementById('update-username-btn');
    const newUsernameInput = document.getElementById('new-username');

    // Elements for password change and registration
    const startKeystrokeRegistrationBtn = document.getElementById('start-keystroke-registration');
    const newPasswordInput = document.getElementById('new-password');
    const typingInput = document.getElementById('typing-input');
    const keystrokeRegistrationSection = document.getElementById('keystroke-registration-section');

    // Elements for typing profile update
    const updateTypingProfileBtn = document.querySelector(".sidebar button[onclick=\"showSection('update-typing-profile-section')\"]");
    const typingProfileUpdateSection = document.getElementById('update-typing-profile-section');
    const typingInputUpdate = document.getElementById('typing-input-update');
    const displayedPasswordElement = document.getElementById('displayed-password');

    const expectedLength = 11; // Expected length of keystroke data
    let typingData = [];
    let updateTypingData = [];
    let currentAttempt = 1;
    let updateCurrentAttempt = 1;
    let tempData = { H: [], DD: [], UD: [] };
    let lastKeydownTime = null;
    let lastKeyupTime = null;

    window.showSection = function (sectionId) {
        document.querySelectorAll('.content-container').forEach(section => section.style.display = 'none');
        document.getElementById(sectionId).style.display = 'block';
    
        // Show or hide keystroke graphs based on selected section
        const keystrokeGraphs = document.getElementById('keystroke-graphs');
        if (sectionId === 'default-section') {
            keystrokeGraphs.style.display = 'block'; // Show graphs on Home section
            renderKeystrokeCharts(); // Render charts when Home section is selected
        } else {
            keystrokeGraphs.style.display = 'none'; // Hide graphs on other sections
        }
    
        resetTypingData(); // Clear any old data each time a new section is shown
    };

    function renderKeystrokeCharts() {
        fetch('/get_keystroke_data')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error(data.error);
                    return;
                }

                console.log("Fetched Keystroke Data:", data);

                // Prepare datasets for each chart
                const holdTimeSessions = data.H.map((session, index) => ({
                    label: `Session ${index + 1}`,
                    data: session,
                    borderColor: getRandomColor(),
                    fill: false,
                }));

                const keydownKeydownTimeSessions = data.DD.map((session, index) => ({
                    label: `Session ${index + 1}`,
                    data: session,
                    borderColor: getRandomColor(),
                    fill: false,
                }));

                const keyupKeydownTimeSessions = data.UD.map((session, index) => ({
                    label: `Session ${index + 1}`,
                    data: session,
                    borderColor: getRandomColor(),
                    fill: false,
                }));

                // Generate labels based on the length of the longest session
                const maxLength = Math.max(
                    ...data.H.map(session => session.length),
                    ...data.DD.map(session => session.length),
                    ...data.UD.map(session => session.length)
                );
                const labels = Array.from({ length: maxLength }, (_, i) => `Key ${i + 1}`);

                // Create each chart
                createChart('holdTimeChart', 'Hold Time', labels, holdTimeSessions);
                createChart('keydownKeydownTimeChart', 'Keydown-Keydown Time', labels, keydownKeydownTimeSessions);
                createChart('keyupKeydownTimeChart', 'Keyup-Keydown Time', labels, keyupKeydownTimeSessions);
            })
            .catch(error => console.error('Error fetching keystroke data:', error));
    }

    function createChart(canvasId, title, labels, datasets) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: title
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Utility function to generate random colors for each session line
    function getRandomColor() {
        const letters = '0123456789ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    }

    renderKeystrokeCharts(); // Call to render the charts

    function fetchLastLoginInfo() {
        fetch('/get_last_login_info')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error(data.error);
                    return;
                }
    
                const lastSuccessful = data.last_successful;
                const lastFailed = data.last_failed;
    
                // Parse UTC time and convert to local timezone
                document.getElementById('last-successful-login').textContent = lastSuccessful.time
                    ? new Date(lastSuccessful.time).toLocaleString()  // Converts UTC to user's local time
                    : 'No successful login recorded';
    
                document.getElementById('last-failed-login').textContent = lastFailed
                    ? new Date(lastFailed).toLocaleString()  // Converts UTC to user's local time
                    : 'No failed login recorded';
    
                // Display match percentages
                fetch('/get_attempt_percentages')
                    .then(response => response.json())
                    .then(data => {
                        const loginAttemptsContainer = document.getElementById('login_attempts_list');
                        loginAttemptsContainer.innerHTML = '';  // Clear previous data

                        if (data.attempt_percentages) {
                            data.attempt_percentages.forEach((percentage, index) => {
                                const attemptItem = document.createElement('li');
                                attemptItem.textContent = `Sign-in Attempt ${index + 1}: ${percentage.toFixed(2)}%`;
                                loginAttemptsContainer.appendChild(attemptItem);
                            });
                        } else {
                            const noAttemptsItem = document.createElement('li');
                            noAttemptsItem.textContent = 'No attempts found.';
                            loginAttemptsContainer.appendChild(noAttemptsItem);
                        }
                    })
                    .catch(error => console.error('Error fetching attempt percentages:', error));
            })
            .catch(error => console.error('Error fetching last login info:', error));
    }
    
    

// Call this function when "Last Login Log" section is displayed
document.querySelector(".nav-btn[onclick=\"showSection('last-login-section')\"]")
    .addEventListener('click', fetchLastLoginInfo);


    // Update username in the database
    updateUsernameBtn.addEventListener('click', () => {
        const newUsername = newUsernameInput.value.trim();
        if (!newUsername) {
            alert('Please enter a new username');
            return;
        }

        fetch('/update_username', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_username: newUsername })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                document.querySelector('#default-section h1').textContent = `Hello, ${newUsername}`;
                newUsernameInput.value = '';
            } else {
                alert(data.error);
            }
        })
        .catch(error => console.error('Error:', error));
    });


    // Utility function to validate password
    function validatePassword(password) {
        const lengthRule = password.length > 5 && password.length <= 11;
        const letterRule = /[a-z]/.test(password);
        const uppercaseRule = /[A-Z]/.test(password);
        const numberRule = /\d/.test(password);
        const symbolRule = /[\W_]/.test(password); // Matches non-alphanumeric characters

        return lengthRule && letterRule && uppercaseRule && numberRule && symbolRule;
    }
    
    // Start keystroke data registration for new password
    startKeystrokeRegistrationBtn.addEventListener('click', () => {
        const newPassword = newPasswordInput.value.trim();
        if (!validatePassword(newPassword)) {
            alert("Password does not meet the required criteria. Please follow the rules below the input box.");
            return;
        }    
        
        // Display the new password as a reference
        document.getElementById('displayed-password').textContent = newPassword;
        
        typingData = []; // Clear any previous keystroke data
        currentAttempt = 1;
        keystrokeRegistrationSection.style.display = 'block';
        document.getElementById('password-change-section').style.display = 'none';
        typingInput.focus();
    });

    // Handle typing input for password change
    typingInput.addEventListener('keydown', function () {
        recordKeydownTime();
    });

    typingInput.addEventListener('keyup', function () {
        recordKeyupTime();
    });

    document.getElementById('next-attempt-btn').addEventListener('click', () => {
        recordKeystrokeData(typingData, typingInput, newPasswordInput.value, 'keystroke-registration-section', submitKeystrokeData);
    });

    function resetTypingData() {
        typingData = [];
        currentAttempt = 1;
        tempData = { H: [], DD: [], UD: [] };
    }

    function recordKeydownTime() {
        const currentTime = performance.now() / 1000;
        if (tempData.H.length < expectedLength) {
            if (lastKeydownTime !== null) {
                const holdTime = currentTime - lastKeydownTime;
                tempData.H.push(holdTime);
            }
            lastKeydownTime = currentTime;
        }
    }

    function recordKeyupTime() {
        const currentTime = performance.now() / 1000;
        if (tempData.UD.length < expectedLength) {
            if (lastKeyupTime !== null) {
                const udTime = currentTime - lastKeyupTime;
                tempData.UD.push(udTime);
            }
            lastKeyupTime = currentTime;
        }
        if (tempData.DD.length < expectedLength) {
            const ddTime = currentTime - lastKeydownTime;
            tempData.DD.push(ddTime);
        }
        lastKeyupTime = currentTime;
    }

    function recordKeystrokeData(dataArray, inputElement, referenceValue, sectionId, submitCallback) {
        const inputValue = inputElement.value.trim();
        if (inputValue !== referenceValue) {
            alert('Password does not match. Please try again.');
            inputElement.value = '';
            return;
        }

        if (tempData.H.length < 1 || tempData.DD.length < 1 || tempData.UD.length < 1) {
            alert('Incomplete typing data. Please retry.');
            inputElement.value = '';
            return;
        }

        // Pad H, DD, and UD arrays to the expected length
        let H_padded = [...tempData.H];
        let DD_padded = [...tempData.DD];
        let UD_padded = [...tempData.UD];

        while (H_padded.length < expectedLength) H_padded.push(0);
        while (DD_padded.length < expectedLength) DD_padded.push(0);
        while (UD_padded.length < expectedLength) UD_padded.push(0);

        dataArray.push({ H: H_padded, DD: DD_padded, UD: UD_padded });
        tempData = { H: [], DD: [], UD: [] };
        inputElement.value = ''; // Clear input for next attempt

        if (dataArray === typingData) {
            if (currentAttempt < 5) {
                currentAttempt++;
                document.querySelector(`#${sectionId} h3`).textContent = `Type your password (Attempt ${currentAttempt} of 5)`;
            } else {
                submitCallback();
            }
        } else if (dataArray === updateTypingData) {
            if (updateCurrentAttempt < 5) {
                updateCurrentAttempt++;
                document.querySelector(`#${sectionId} h3`).textContent = `Type your password (Attempt ${updateCurrentAttempt} of 5)`;
            } else {
                submitCallback();
            }
        }
    }

    function submitKeystrokeData() {
        fetch('/change_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: newPasswordInput.value,
                typing_sessions: typingData
            })
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            if (data.success) {
                resetTypingData();
                document.getElementById('keystroke-registration-section').style.display = 'none';
            }
        })
        .catch(error => console.error('Error:', error));
    }

    // Display section to update the keystroke profile with current password
    updateTypingProfileBtn.addEventListener('click', () => {
        fetch('/get_current_password')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayedPasswordElement.textContent = data.password;  // Show password for reference
                    typingProfileUpdateSection.style.display = 'block';
                    resetUpdateTypingData();
                } else {
                    alert('Unable to retrieve current password. Please try again.');
                }
            })
            .catch(error => console.error('Error fetching current password:', error));
    });


    function resetUpdateTypingData() {
        updateTypingData = [];
        updateCurrentAttempt = 1;
        tempData = { H: [], DD: [], UD: [] };
        typingInputUpdate.value = '';
    }

    // Record keystroke data for update profile
    typingInputUpdate.addEventListener('keydown', (event) => {
        recordKeydownTime();
    });

    typingInputUpdate.addEventListener('keyup', (event) => {
        recordKeyupTime();
    });

    document.getElementById('next-attempt-update-btn').addEventListener('click', () => {
        recordKeystrokeData(updateTypingData, typingInputUpdate, displayedPasswordElement.textContent.trim(), 'update-typing-profile-section', submitUpdateKeystrokeData);
    });

    function submitUpdateKeystrokeData() {
        fetch('/update_typing_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ typing_sessions: updateTypingData })
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            if (data.success) {
                resetUpdateTypingData();
                typingProfileUpdateSection.style.display = 'none';
            }
        })
        .catch(error => console.error('Error:', error));
    }

    // Sign out function
    function signOut() {
        window.location.href = '/';
    }

    // Attach sign out button event
    document.getElementById('sign-out-btn').addEventListener('click', signOut);
});
