
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os

st.set_page_config(layout="wide", page_title="Employee Dashboard")

CSV_PATH = r"C:\Users\lek\OneDrive\Desktop\EmployeeDashboard\employee_data.csv"
ADMIN_USER = "admin"
ADMIN_PASS = "1234"
MONTHLY_LEAVE_QUOTA = 5
@st.cache_data
def load_data(path):
    df_local = pd.read_csv(path)
    # normalize column names
    df_local.columns = [c.strip() for c in df_local.columns]
    return df_local

try:
    df = load_data(CSV_PATH)
except Exception as e:
    st.error(f"Cannot read CSV at `{CSV_PATH}`. Error: {e}")
    st.stop()

if "employee_id" not in df.columns:
    st.error("CSV must contain column: 'employee_id'. Please check your CSV header.")
    st.stop()

if "Used_Leaves" not in df.columns:
    df["Used_Leaves"] = 0

df["Attendance_Percentage"] = pd.to_numeric(df["Attendance_Percentage"], errors="coerce").fillna(0)
df["Avg_Task_Rating"] = pd.to_numeric(df["Avg_Task_Rating"], errors="coerce").fillna(0)
df["employee_id"] = df["employee_id"].astype(str).str.strip()


df["_password"] = df["employee_id"].str[-2:]

if "credentials" not in st.session_state:
    creds = {}
    for uid in df["employee_id"].tolist():
        creds[uid] = {"password": uid[-2:], "role": "employee"}
    creds[ADMIN_USER] = {"password": ADMIN_PASS, "role": "admin"}
    st.session_state.credentials = creds

if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

if "leave_balance" not in st.session_state:
    lb = {}
    for uid in df["employee_id"].tolist():
        used = int(pd.to_numeric(df.loc[df["employee_id"] == uid, "Used_Leaves"], errors="coerce").fillna(0).sum())
        lb[uid] = max(0, MONTHLY_LEAVE_QUOTA - used)
    st.session_state.leave_balance = lb

if "leave_history" not in st.session_state:
    hist = {}
    for uid in df["employee_id"].tolist():
        hist[uid] = pd.DataFrame(columns=["Date", "Days", "Reason", "Status"])
    st.session_state.leave_history = hist

if "leave_requests" not in st.session_state:
    st.session_state.leave_requests = pd.DataFrame(columns=["RequestID", "EmployeeID", "Date", "Days", "Reason", "Status"])

def save_used_leaves_to_csv():
    """Write back Used_Leaves to CSV so approvals persist across restarts."""
    try:
 
        for uid, remaining in st.session_state.leave_balance.items():
            used = MONTHLY_LEAVE_QUOTA - remaining
            df.loc[df["employee_id"] == uid, "Used_Leaves"] = int(used)
        df.to_csv(CSV_PATH, index=False)
    except Exception as e:
        st.warning(f"Could not save to CSV: {e}")

def next_request_id():
    if st.session_state.leave_requests.empty:
        return 1
    return int(st.session_state.leave_requests["RequestID"].max()) + 1


st.sidebar.title("Employee Dashboard")
if st.session_state.user is None:
    with st.sidebar.form("login_form"):
        st.sidebar.write("Login")
        uid_input = st.text_input("Employee ID or Admin", key="uid_input")
        pwd_input = st.text_input("Password", type="password", key="pwd_input")
        submitted = st.form_submit_button("Login")
        if submitted:
            uid = str(uid_input).strip()
            if uid in st.session_state.credentials and st.session_state.credentials[uid]["password"] == pwd_input:
                st.session_state.user = uid
                st.session_state.role = st.session_state.credentials[uid]["role"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()
else:
    st.sidebar.markdown(f"**Logged in:** `{st.session_state.user}`")
    st.sidebar.markdown(f"**Role:** `{st.session_state.role}`")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

current_user = st.session_state.user
current_role = st.session_state.role

if current_role == "employee":
    st.header("My Dashboard")
    uid = current_user
    emp_rows = df[df["employee_id"] == uid]
    if emp_rows.empty:
        st.error("Your employee ID was not found in the CSV.")
        st.stop()
    emp = emp_rows.iloc[0]

    name_display = emp.get("Name", emp.get("name", uid))
    st.subheader(f"{name_display}  (ID: {uid})")
    st.write(f"📅 Days Present: {int(emp.get('Days_Present',0))}")
    st.write(f"📈 Attendance %: {float(emp.get('Attendance_Percentage',0)):.2f}")
    st.write(f"⭐ Avg Task Rating: {float(emp.get('Avg_Task_Rating',0)):.1f}")
    st.write(f"ℹ Insight: {emp.get('Insight','-')}")

   
    c1, c2 = st.columns(2)
    with c1:
        fig, ax = plt.subplots()
        sns.barplot(x=["Attendance %"], y=[float(emp.get('Attendance_Percentage',0))], ax=ax)
        ax.set_ylim(0,100)
        ax.set_ylabel("Attendance %")
        st.pyplot(fig)
    with c2:
        fig2, ax2 = plt.subplots()
        sns.barplot(x=["Avg Task Rating"], y=[float(emp.get('Avg_Task_Rating',0))], ax=ax2)
        ax2.set_ylim(0,10)
        ax2.set_ylabel("Rating")
        st.pyplot(fig2)

    st.markdown("---")
    st.subheader("Leave Management")
    remaining = st.session_state.leave_balance.get(uid, MONTHLY_LEAVE_QUOTA)
    used = MONTHLY_LEAVE_QUOTA - remaining
    st.info(f"Used: {used}  |  Remaining: {remaining}")

    with st.form("leave_form"):
        days = st.number_input("Days to apply", min_value=1, max_value=MONTHLY_LEAVE_QUOTA, value=1)
        reason = st.text_area("Reason (optional)", max_chars=250)
        applied = st.form_submit_button("Apply for Leave")
        if applied:
            # add pending request (do not deduct balance yet)
            rid = next_request_id()
            new_req = {
                "RequestID": rid,
                "EmployeeID": uid,
                "Date": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "Days": int(days),
                "Reason": reason,
                "Status": "Pending"
            }
            st.session_state.leave_requests.loc[len(st.session_state.leave_requests)] = new_req
            # add to employee history as pending
            st.session_state.leave_history[uid].loc[len(st.session_state.leave_history[uid])] = {
                "Date": new_req["Date"],
                "Days": new_req["Days"],
                "Reason": reason,
                "Status": "Pending"
            }
            st.success("Leave request submitted (Pending). Admin will review.")
            st.rerun()

    st.markdown("---")
    st.subheader("My Leave History")
    hist_df = st.session_state.leave_history.get(uid, pd.DataFrame(columns=["Date","Days","Reason","Status"]))
    st.dataframe(hist_df.sort_values(by="Date", ascending=False).reset_index(drop=True))

elif current_role == "admin":
    st.header("Admin Dashboard")
    # KPIs
    avg_att = df["Attendance_Percentage"].astype(float).mean()
    avg_rating = df["Avg_Task_Rating"].astype(float).mean()
    pending = st.session_state.leave_requests[st.session_state.leave_requests["Status"] == "Pending"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Attendance %", f"{avg_att:.2f}")
    c2.metric("Avg Task Rating", f"{avg_rating:.2f}")
    c3.metric("Pending Requests", len(pending))

    st.markdown("---")
    st.subheader("Attendance Chart")
    fig, ax = plt.subplots(figsize=(10,4))
    sns.barplot(x=df["employee_id"].astype(str), y=df["Attendance_Percentage"].astype(float), ax=ax)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
    st.pyplot(fig)

    st.markdown("---")
    st.subheader("Pending Leave Requests")
    if pending.empty:
        st.info("No pending requests.")
    else:
        for idx, row in pending.iterrows():
            with st.container():
                st.write(f"ReqID: **{row['RequestID']}**  — Emp: **{row['EmployeeID']}**  — Days: **{row['Days']}**  — Date: {row['Date']}")
                st.write(f"Reason: {row['Reason']}")
                a_col, r_col = st.columns([1,1])
                if a_col.button("Approve", key=f"a_{int(row['RequestID'])}"):
                    empk = str(row["EmployeeID"])
                    days = int(row["Days"])
                    if st.session_state.leave_balance.get(empk,0) >= days:
                        # deduct balance
                        st.session_state.leave_balance[empk] -= days
                        # update central request
                        st.session_state.leave_requests.at[idx, "Status"] = "Approved"
                        # update employee history
                        hdf = st.session_state.leave_history[empk]
                        mask = (hdf["Days"]==days) & (hdf["Status"]=="Pending")
                        if mask.any():
                            ixs = hdf[mask].index
                            st.session_state.leave_history[empk].at[ixs[0], "Status"] = "Approved"
                        # persist used leaves back to CSV
                        save_used_leaves_to_csv()
                        st.success(f"Approved request {row['RequestID']} for {empk}")
                        st.rerun()
                    else:
                        st.error("Not enough remaining leaves to approve.")
                if r_col.button("Reject", key=f"r_{int(row['RequestID'])}"):
                    empk = str(row["EmployeeID"])
                    st.session_state.leave_requests.at[idx, "Status"] = "Rejected"
                    # update employee history
                    hdf = st.session_state.leave_history[empk]
                    mask = (hdf["Days"]==int(row["Days"])) & (hdf["Status"]=="Pending")
                    if mask.any():
                        ixs = hdf[mask].index
                        st.session_state.leave_history[empk].at[ixs[0], "Status"] = "Rejected"
                    st.success(f"Rejected request {row['RequestID']} for {empk}")
                    st.rerun()

    st.markdown("---")
    st.subheader("All Employees Data")
    st.dataframe(df.reset_index(drop=True))

    st.markdown("---")
    st.subheader("Leave Balances")
    lb_df = pd.DataFrame([{"EmployeeID":k, "Remaining":v} for k,v in st.session_state.leave_balance.items()])
    st.dataframe(lb_df.sort_values(by="EmployeeID").reset_index(drop=True))

else:
    st.error("Unknown role — please logout and login again.")
