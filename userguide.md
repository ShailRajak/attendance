# IIPL Enterprise eHR Portal - User Guide

Welcome to the **IIPL Enterprise eHR Portal**, a modern, responsive, and feature-rich Web Application designed to manage employee attendance, overtime, leaves, and workspace feedback.

This guide provides instructions on how to register, log in, navigate, and utilize all the key features of the application, tailored for both standard **Employees** and **Administrators / Supervisors**.

---

## Table of Contents
1. [Overview & Key Features](#1-overview--key-features)
2. [Account Setup: Sign Up & Log In](#2-account-setup-sign-up--log-in)
3. [For Employees: How to Use the Portal](#3-for-employees-how-to-use-the-portal)
4. [For Administrators & Supervisors: Management Features](#4-for-administrators--supervisors-management-features)
5. [Interface Customization (Light/Dark Theme)](#5-interface-customization-lightdark-theme)

---

## 1. Overview & Key Features

The eHR Portal links directly with your site's physical biometric scanners to aggregate real-time metrics.

*   **Attendance Dashboard**: Live summary of active headcount, shift metrics (Day/Night shifts), and list of daily check-in/check-out logs.
*   **Overtime (OT) Dashboard**: Detailed tracking of system-calculated (card punch) OT, pre-approved (requested) OT, weekend work, and holiday work with customizable visual alert thresholds (Low, Medium, High).
*   **Leaves Dashboard**: Auto-classification of attendance logs into categories like *Full Day*, *Half Day*, *Short Leave* (2-hour delay/early exit), *Absent*, and *Rest Day / Holiday*.
*   **Feedback Channel**: Secure submission form for employees to report suggestions, complaints, or errors directly to the system administrators.
*   **Administration Control Panel**: Central node for managing organizational Hierarchies (Companies, Plants, Departments, Sections, Teams), Role-Based Access Controls (RBAC), database configuration, and bulk data imports.

---

## 2. Account Setup: Sign Up & Log In

### Registration (Sign Up)
If you do not have an account yet, register through the signup portal:
1. Click **Sign Up** on the login page or navigate directly to `/signup/`.
2. Fill in the registration form:
   *   **Employee ID**: Your unique company identification number (this will be your username).
   *   **Password / Confirm Password**: Pick a secure password.
   *   **Role**: Select your job classification.
   *   **Plant**: Choose your primary plant location (e.g., **Sector 63 (S63)** or **Phase 2 (C39)**).
   *   **Section & Team**: Select the specific work area and team you are assigned to.
3. Click **Sign Up** to create your account and automatically log in.

### Logging In
1. Go to the login page (`/login/`).
2. Input your **Employee ID** and **Password**.
3. Click **Login** to enter the portal.

---

## 3. For Employees: How to Use the Portal

### Checking Your Attendance
Once logged in, you will land on the **Dashboard Overview**:
*   The header displays your name, Employee ID, mobile number, plant, section, and shift details.
*   **Overview Cards**: View your total working days, days present, leaves taken, late arrivals, mispunches, and average work hours for the current cycle.
*   **Attendance Logs**: Scroll down to view daily details: date, weekday, check-in, check-out, working hours, overtime hours, and classification status.
*   **Date Range Filtering**: Use the **Adjust Period & Search** button at the top-right to filter records for a custom date range.
*   **Calendar View**: Toggle to the **Calendar View** to see a color-coded calendar summarizing your monthly attendance patterns.

### Viewing Your Overtime (OT)
Click on **Overtime** in the sidebar navigation:
*   View your **Card Punch OT** (system calculated), **Requested OT**, **Weekend OT**, and **Holiday OT** totals.
*   The dashboard dynamically tags your total overtime load (e.g., **Low**, **Medium**, **High**) based on company limits.
*   The **Overtime Trend** chart shows your daily overtime hours over the selected period.

### Submitting Workspace Feedback
If you need to submit suggestions, report attendance discrepancies, or file queries:
1. Click **Feedback** in the sidebar.
2. Select your **Plant Location** (defaulted from your profile).
3. Type your comments in the **Feedback / Suggestions** box.
4. Click **Submit Feedback**. 
   *(Note: This feedback is highly secure and is only visible to the system superadministrators).*

---

## 4. For Administrators & Supervisors: Management Features

As an administrator or supervisor, your portal functions differently to give you organizational oversight.

### Supervisor Dashboard
*   **Group View**: When you log in, the home dashboard shows a group-wide overview of all employees in your scope (by default, showing metrics for the previous day).
*   **Enterprise KPI Cards**: Shows real-time summaries:
    *   *Total Headcount*
    *   *Day & Night Shift splits*
    *   *Present Day / Present Night counts*
    *   *Absent, On Leave, and Late Punch totals*
*   **Search**: Use the **Adjust Period & Search** dropdown to query attendance details for a specific employee ID.

### Overtime & Leaves Scopes
*   **Section View**: The Overtime and Leaves tabs aggregate information across all employees under your supervisory scope.
*   You will see a list of employee names, their individual subtotals, and a **Scope Total** row summarizing the entire section.

### Viewing Employee Feedbacks
Superadmins can view employee suggestions directly on the portal:
1. Click **Feedback** in the sidebar.
2. Instead of the form, you will see a detailed tabular list of all feedback submissions containing **Employee ID**, **Plant Location**, **Feedback Details**, and the **Submitted Date/Time**.

### Django Admin Control Panel
To manage configuration models, roles, or users:
1. Click **Administration** in the sidebar or go directly to `/admin/`.
2. Here, you can:
   *   Create and configure users, profiles, sections, teams, and plants.
   *   Adjust system-wide parameters (e.g., **Overtime Limit Configuration** or **Attendance API Configuration**).
   *   Assign permissions and roles dynamically.

---

## 5. Interface Customization (Light/Dark Theme)

The portal supports a high-contrast dark theme and a premium light theme.
*   To switch modes, click the **Sun/Moon icon** at the top right of the navigation header.
*   Your preference is saved locally, so it will persist the next time you log in.
