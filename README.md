# Secure Database-as-a-Service (DBaaS) System
A secure intermediary application designed to protect sensitive healthcare data stored in an untrusted cloud environment. This system implements rigorous cryptography to ensure confidentiality, integrity, and query completeness while maintaining usability through Role-Based Access Control (RBAC).

## Key security features

### User Authentication
- Secure registration & login  
- `bcrypt` password hashing  
- Session security via **JWT (JSON Web Tokens)**  

### Role-Based Access Control (RBAC)
- **Group H (Doctors/Nurses):** Full access (add + view)  
- **Group R (Researchers):** View-only with **PII redaction** (names → `***`)  

### Data Confidentiality
Sensitive fields encrypted using **AES-GCM** (randomized encryption):
- Gender  
- Age  

### Data Integrity
- Each row includes an **HMAC-SHA256** signature  
- Detects single-bit modifications  

### Query Completeness
- Implemented using a **cryptographic hash chain**  
- Detects row omission or deletion  

### Order Preserving Encryption (OPE)
- Weight values encrypted using **OPE**  
- Supports range queries like:  
  ```sql
  WHERE weight BETWEEN 60 AND 70;
  ```
## Tech Stack

### **Backend**
- Python  
- Flask  

### **Database**
- MySQL (Hosted on Aiven Cloud)

### **Frontend**
- HTML5  
- CSS3  
- Vanilla JavaScript (SPA Architecture)

### **Cryptography**
- `cryptography` (AES)  
- `pyope` (OPE)  
- `hashlib`  
- `hmac`
  `
## Setup & Installation

### 1. Prerequisites
- Python **3.8+**
- A MySQL Database (Local or Cloud)

---

### 2. Clone and Install Dependencies

```bash
git clone <repository_url>
cd dspProject
python -m venv venv
source venv/bin/activate     # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
### 3. Configuration
Create a config.py file in the root directory. Do not share this file.
```bash
# config.py
DB_USER = 'your_db_user'
DB_PASSWORD = 'your_db_password'
DB_HOST = 'your_db_host'
DB_PORT = 12345
DB_NAME = 'defaultdb'

# Security Keys (Must be bytes)
JWT_SECRET_KEY = 'your-super-secret-jwt-key'
ENCRYPTION_KEY = b'YOUR_32_BYTE_AES_KEY_HERE'
HMAC_KEY = b'YOUR_32_BYTE_HMAC_KEY_HERE'
OPE_KEY_SEED = b'YOUR_32_BYTE_OPE_KEY_HERE'
```
## Required Certificate for Aiven (imp)
Create a directory:
```
certs/
```
Place your Aiven CA certificate inside it:
```
certs/ca.pem
```
Your connection logic checks for it:
```
print("Connecting to Aiven database...")
cnx = database.get_db_connection()
if not cnx:
    print("Connection failed. Check your config.py and certs/ca.pem file.")
    return
```
### 5. Initialize Database
Run the setup script to create tables and populate initial mock data.
Warning: This wipes existing data in the healthcare table.
```
python scripts/populate_db.py
```
## Running the Application

You need **two terminals** running simultaneously.

---

### **Terminal 1 — Backend API**

```bash
python run.py
# Runs on http://localhost:5000
```
### **Terminal 2 — Frontend Client**

```bash
cd frontend
python -m http.server 8000
# Runs on http://localhost:8000
```
## How to Test

Open your browser and navigate to:

**http://localhost:8000**

---

### Register Users
- Create a **Doctor (Group H)**
- Create a **Researcher (Group R)**

---

### Test Access Control
- Log in as **Researcher**
- Observe that names are redacted as `***`

---

### Test OPE (Order-Preserving Encryption)
- Log in as **Doctor**
- Use the **"Search by Weight"** feature to filter encrypted data

---

### Test Integrity (HMAC)
- Manually edit a row in your SQL database (e.g., change a weight value)
- Refresh the frontend → the row will be **hidden** because the HMAC validation fails

---

### Test Completeness (Hash Chain)
- Manually **delete a row** in your SQL database
- The frontend will show: **"Fatal Error: Chain Broken"**

### Team Members
- Mounika Seelam
- Amitha Ajithkumar
- Prajwal Devaraj
