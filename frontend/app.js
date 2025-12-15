// here waiting for the DOM (HTML) to be fully loaded
document.addEventListener("DOMContentLoaded", () => {

    // this is brain of our app.
    // we store the API URL and the user's token here.
    let API_URL;

    if (window.location.hostname.endsWith(".app.github.dev")) {
        // Codespace case: map 8000 → 5000
        API_URL = `https://${window.location.hostname.replace(/-\d+\.app\.github\.dev$/, "-5000.app.github.dev")}`;
    } else {
        // Local case
        API_URL = `${window.location.protocol}//${window.location.hostname}:5000`;
    }

    console.log("API_URL =", API_URL);

    let authToken = null;
    let authUser = {
        username: null,
        group: null
    };

    // DOM ELEMENTS
    // getting references to all the elements we need to interact with
    // page containers
    const pageLogin = document.getElementById("page-login");
    const pageRegister = document.getElementById("page-register");
    const pageApp = document.getElementById("page-app");

    // login form
    const loginForm = document.getElementById("login-form");
    const loginUsernameInput = document.getElementById("login-username");
    const loginPasswordInput = document.getElementById("login-password");

    // register form
    const registerForm = document.getElementById("register-form");
    const registerUsernameInput = document.getElementById("register-username");
    const registerPasswordInput = document.getElementById("register-password");
    const registerOccupationInput = document.getElementById("register-occupation");

    // navigation / session
    const userSessionDiv = document.getElementById("user-session");
    const sessionUsernameSpan = document.getElementById("session-username");
    const logoutButton = document.getElementById("logout-button");

    // links
    const showRegisterLink = document.getElementById("show-register-link");
    const showLoginLink = document.getElementById("show-login-link");

    // message container
    const messageContainer = document.getElementById("message-container");

    // add patient elements
    const addPatientForm = document.getElementById("add-patient-form");
    const pFirst = document.getElementById("p-first");
    const pLast = document.getElementById("p-last");
    const pGender = document.getElementById("p-gender");
    const pAge = document.getElementById("p-age");
    const pWeight = document.getElementById("p-weight");
    const pHeight = document.getElementById("p-height");
    const pHistory = document.getElementById("p-history");

    // searching elements
    const searchMin = document.getElementById("search-min");
    const searchMax = document.getElementById("search-max");
    const btnSearchWeight = document.getElementById("btn-search-weight");
    const btnViewAll = document.getElementById("btn-view-all");

    // other app elements
    const appContent = document.getElementById("app-content");
    const appUsernameSpan = document.getElementById("app-username");
    const addPatientContainer = document.getElementById("add-patient-container");

    // helper functions
    /**
     * showing a message to the user (eg., "Login failed")
     * @param {string} text the message to show
     * @param {string} type "success" or "error"
     */
    function showMessage(text, type = "error") {
        messageContainer.textContent = text;
        messageContainer.className = `message ${type}`;
        // hiding the message after 3 seconds
        setTimeout(() => {
            messageContainer.className = "message hidden";
        }, 3000);
    }

    /**
     * hides all "pages" and shows only the one with the given ID
     * @param {string} pageId "page-login", "page-register", or "page-app"
     */
    function showPage(pageId) {
        // hide all pages
        pageLogin.classList.add("hidden");
        pageRegister.classList.add("hidden");
        pageApp.classList.add("hidden");

        // show the requested page
        const pageToShow = document.getElementById(pageId);
        if (pageToShow) {
            pageToShow.classList.remove("hidden");
        }
    }

    /**
     * updating the UI to show the user is logged in
     */
    function updateUIForLogin() {
        sessionUsernameSpan.textContent = `Welcome, ${authUser.username} (Group ${authUser.group})`;
        sessionUsernameSpan.classList.remove("hidden");
        logoutButton.classList.remove("hidden");
        appUsernameSpan.textContent = authUser.username;

        // access control for adding patients
        if (authUser.group === 'H') {
            addPatientContainer.classList.remove("hidden"); // Doctors can add
        } else {
            addPatientContainer.classList.add("hidden"); // Researchers cannot add
        }

        showPage("page-app");

        console.log("UI updated for login. User:", authUser);
    }

    /**
     * Resets the UI to a logged-out state
     */
    function updateUIForLogout() {
        authToken = null;
        authUser = { username: null, group: null };

        sessionUsernameSpan.textContent = "";
        sessionUsernameSpan.classList.add("hidden");
        logoutButton.classList.add("hidden");

        appContent.innerHTML = '<p style="color: #666;">Click "View All Patients" or Search to see data.</p>';

        // clearing search inputs
        if (searchMin) searchMin.value = "";
        if (searchMax) searchMax.value = "";

        // clearing add patient form
        if (addPatientForm) addPatientForm.reset();

        // showing the login page
        showPage("page-login");
        console.log("UI updated for logout.");
    }

    function renderTable(data) {
        if (!data || data.length === 0) {
            appContent.innerHTML = "<p>No records found.</p>";
            return;
        }

        const processedData = data.map(row => {
            if (authUser.group === 'R') {
                return { ...row, first_name: '***', last_name: '***' };
            }
            return row;
        });

        let html = `
    <table border="1" style="border-collapse: collapse; width: 100%;">
    <thead>
        <tr>
        <th>ID</th><th>First Name</th><th>Last Name</th>
        <th>Gender</th><th>Age</th><th>Weight</th>
        <th>Height</th><th>Health History</th>
        </tr>
    </thead>
    <tbody>
    `;
        processedData.forEach(row => {
            let gender = row.gender;
            if (row.gender === true || row.gender === "true") gender = "Male";
            if (row.gender === false || row.gender === "false") gender = "Female";
            html += `
        <tr>
            <td>${row.patient_id}</td>
            <td>${row.first_name}</td>
            <td>${row.last_name}</td>
            <td>${gender}</td>
            <td>${row.age}</td>
            <td>${row.weight}</td>
            <td>${row.height}</td>
            <td>${row.health_history}</td>
        </tr>`;
        });
        html += "</tbody></table>";

        appContent.innerHTML = html;
    }

    // API FUNCTIONS

    async function handleLogin(event) {
        event.preventDefault();
        const username = loginUsernameInput.value;
        const password = loginPasswordInput.value;

        try {
            const response = await fetch(`${API_URL}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Login failed");

            authToken = data.token;
            // decoding token manually to get group
            const payload = JSON.parse(atob(authToken.split('.')[1]));
            authUser.username = payload.username;
            authUser.group = payload.group;

            updateUIForLogin();
            showMessage("Login successful!", "success");
        } catch (err) {
            showMessage(err.message, "error");
        }
    }

    async function handleRegister(event) {
        event.preventDefault();
        const username = registerUsernameInput.value;
        const password = registerPasswordInput.value;
        const occupation = registerOccupationInput.value;

        try {
            const response = await fetch(`${API_URL}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password, occupation })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Register failed");

            showMessage("Registration successful! Please login.", "success");
            registerForm.reset();
            showPage("page-login");
        } catch (err) {
            showMessage(err.message, "error");
        }
    }

    async function handleViewAll() {
        appContent.innerHTML = "<p>Loading...</p>";
        try {
            const response = await fetch(`${API_URL}/query_all`, {
                headers: { "Authorization": `Bearer ${authToken}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Query failed");

            renderTable(data);
        } catch (err) {
            appContent.innerHTML = `<p style="color:red; font-weight:bold;">Error: ${err.message}</p>`;
        }
    }

    async function handleSearchWeight() {
        const min = searchMin.value;
        const max = searchMax.value;
        if (!min || !max) {
            showMessage("Please enter both Min and Max weight", "error");
            return;
        }

        appContent.innerHTML = "<p>Searching (OPE Encrypted)...</p>";
        try {
            const response = await fetch(`${API_URL}/query_by_weight?min=${min}&max=${max}`, {
                headers: { "Authorization": `Bearer ${authToken}` }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Search failed");

            renderTable(data);
        } catch (err) {
            appContent.innerHTML = `<p style="color:red; font-weight:bold;">Error: ${err.message}</p>`;
        }
    }

    async function handleAddPatient(event) {
        event.preventDefault();

        const payload = {
            first_name: pFirst.value,
            last_name: pLast.value,
            gender: pGender.value === "true", // converting string to boolean
            age: parseInt(pAge.value),
            weight: parseFloat(pWeight.value),
            height: parseFloat(pHeight.value),
            health_history: pHistory.value
        };

        try {
            const response = await fetch(`${API_URL}/add_data`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${authToken}`
                },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Add failed");

            showMessage("Patient added successfully!", "success");
            addPatientForm.reset();
            // Refresh table
            await handleViewAll();
        } catch (err) {
            showMessage(err.message, "error");
        }
    }

    // event listeners
    loginForm.addEventListener("submit", handleLogin);
    registerForm.addEventListener("submit", handleRegister);
    addPatientForm.addEventListener("submit", handleAddPatient);

    btnViewAll.addEventListener("click", handleViewAll);
    btnSearchWeight.addEventListener("click", handleSearchWeight);

    showRegisterLink.addEventListener("click", (e) => { e.preventDefault(); showPage("page-register"); });
    showLoginLink.addEventListener("click", (e) => { e.preventDefault(); showPage("page-login"); });
    logoutButton.addEventListener("click", updateUIForLogout);

    // start
    updateUIForLogout();
});