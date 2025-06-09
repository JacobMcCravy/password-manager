**This project is for CIS2619. Use at your own risk.**

**1. Create Project Directory**
Open Command Prompt as Administrator and run:
cd C:\temp
mkdir password-manager
cd password-manager

**2. Install Python 3.10 or Newer**
Download from https://www.python.org/downloads/windows/, run installer, check "Add Python to PATH".
Verify installation:
python --version

**3. Set Up Python Virtual Environment**
Run:
python -m venv venv
venv\Scripts\activate

**4. Install Dependencies**
Install dependencies:
pip install --upgrade pip
pip install -r requirements.txt

**5. Install & Initialize MySQL Server**
Download and run MySQL Installer (Developer Default), set root password.
Verify:
mysql --version

**6. Create Environment File (.env)**
Edit .env:
Create encryption key in powershell: [System.BitConverter]::ToString((1..32 | ForEach-Object {Get-Random -Minimum 0 -Maximum 256}) -as [byte[]]).Replace("-", "").ToLower()
Add your ENCRYPTION_KEY, DB_USER and DB_PASSWORD

**7. Initialize the Database**
Using MySQL CLI:
mysql -u root -p
SOURCE "C:/temp/password-manager/schema.sql";

**8. Run the Application**
Activate virtual environment and start Flask:
cd C:\temp\password-manager
venv\Scripts\activate
flask run
Visit http://localhost:5000




