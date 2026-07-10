# IIPL Enterprise eHR Portal - Standard Operating Procedure (SOP)

This document outlines the **Standard Operating Procedures (SOP)** for the deployment, configuration, administration, maintenance, and troubleshooting of the IIPL Enterprise eHR Portal.

---

## 1. System Architecture & Context

The application is built using a modern decoupled architecture:
*   **Web Framework**: Django 6.0.6 (Python 3.14).
*   **Database**: SQLite (`db.sqlite3` in project root).
*   **Biometric Integration**: Leverages direct HTTP POST queries to an external REST biometric service (`http://10.61.248.6:18010/RESTService/Search`) to fetch real-time punches.
*   **Caching**: Employs Python's caching system with a default timeout of 1 hour (`3600 seconds`) to cache API responses and avoid hitting external hardware excessively.
*   **PWA**: Implements offline service-worker caching (`sw.js`) and application manifest (`manifest.json`) for installation on mobile devices.

---

## 2. Onboarding Employees

To onboard a new employee or supervisor:
1.  **Registration**: Direct the employee to navigate to the sign-up page (`/signup/`).
2.  **Required Profile Data**: Ensure the employee selects the correct plant (**Sector 63** or **Phase 2**), department, section, and team.
3.  **Role Assignment**: Assign the appropriate role.
    *   *Standard Employee*: Scope of data visibility defaults to `OWN` (they only see their own logs).
    *   *Supervisor / Manager*: Scope of data visibility defaults to `SECTION` or `DEPARTMENT`.
    *   *Superadmin*: Scope defaults to `ALL`.
4.  **Admin Verification**:
    *   Navigate to the Admin Panel (`/admin/`).
    *   Click on **User Profiles**.
    *   Confirm the employee ID is mapped to the exact numeric ID stored in the physical biometric machine.

---

## 3. Configuring Overtime (OT) Limits

The OT thresholds classify employee workload into **Low**, **Medium**, and **High** ranges. These parameters are stored in the database dynamically (rather than hardcoded in templates).

### How to Update OT Thresholds:
1. Log in to the portal as `Admin` and go to `/admin/`.
2. Scroll to the **Attendance** section and click **Overtime Limit Configurations**.
3. Edit the existing configuration record:
   *   **OT Low Limit** (Default: `52.0` hours): Overtime hours below this are flagged as **Low**.
   *   **OT Medium Limit** (Default: `78.0` hours): Overtime hours below this (and above the low threshold) are flagged as **Medium**. Hours exceeding this limit are flagged as **High**.
4. Click **Save**. The dashboard will immediately reflect the new thresholds.

---

## 4. Biometric API Connection Maintenance

If the IP address or port of the external biometric database server shifts:
1. Go to the Admin Panel (`/admin/`).
2. Click **Attendance API Configurations**.
3. Edit the URL and port mapping parameters:
   *   **API URL** (e.g., `http://10.61.248.6`): Do *not* include the trailing slash or port.
   *   **Port** (e.g., `18010`).
4. Click **Save**. The service layer will dynamically compile queries using the updated address.

---

## 5. Retrieving Employee Feedback

Employees can submit suggestions or attendance correction queries via the **Feedback** sidebar button.
*   **Supervisor / Admin access**: Go to the **Feedback** sidebar page. Because your account is flagged as a superuser, the portal will bypass the submission form and display a tabular ledger of all employee feedbacks.
*   **Admin Panel access**: Navigate to `/admin/` ➔ **Feedbacks** to view, export, or delete records.
*   **Security Boundary**: Only accounts where `is_superuser = True` can view or access this data model.

---

## 6. Database Maintenance & Backup Procedures

### Local Database Backup
To prevent data loss, the SQLite database should be backed up regularly:
1. Stop the Django development server (`Ctrl+C`).
2. Copy the `db.sqlite3` file from the `ehr/` directory to a secure backup directory.
3. Restart the server: `python manage.py runserver 0.0.0.0:8000`.

### Applying Database Schema Changes
If you modify `ehr/attendance/models.py`:
1. Open PowerShell or Command Prompt in the `ehr/` directory.
2. Initialize the virtual environment Python interpreter:
   ```bash
   ..\myenv\Scripts\python.exe manage.py makemigrations
   ```
3. Apply migrations to update the database schema:
   ```bash
   ..\myenv\Scripts\python.exe manage.py migrate
   ```

---

## 7. Troubleshooting Guide

### Issue: Dashboard is displaying 0 statistics or "No logs found for this period"
*   **Check VPN/Network Connectivity**: The biometric server (`10.61.248.6`) is in a private network range. Verify that the host server is on the corporate intranet or VPN.
*   **Verify Employee ID Mapping**: Check if the logged-in user's username is a valid numeric ID (e.g., `19105203`). Standard textual usernames (like `Admin`) will yield `0` records because no matching punches exist in the biometric machine.

### Issue: "TemplateSyntaxError: Invalid block tag... 'endif'"
*   **Reason**: Auto-formatters split template conditional blocks (e.g., `{% if ... %}`) across multiple lines.
*   **Resolution**: Re-merge split conditional tags onto a single line. Django templates do *not* support multi-line block tags.

### Issue: Text inside tables is invisible / hard to read
*   **Reason**: Cell classes overriding text colors in dark theme.
*   **Resolution**: Verify that the `.table-custom td` class in `base.html` has `background: transparent !important;` and `color: var(--text-main) !important;` applied.
