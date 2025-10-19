import streamlit as st
import pandas as pd
import datetime
import pytz
import hashlib
import os
import json

# --- Config ---
OWNER_USERNAME = "vineeth"
OWNER_PASSWORD_HASH = hashlib.sha256("panda@2006".encode()).hexdigest()
DB_FILE = "membership_data.xlsx"
CRED_FILE = "staff_credentials.json"
IST = pytz.timezone('Asia/Kolkata')

# --- Utils ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_ist_time():
    return datetime.datetime.now(IST)

# --- Persistence ---
def load_staff_credentials():
    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    else:
        save_staff_credentials({})
        return {}

def save_staff_credentials(creds):
    with open(CRED_FILE, 'w') as f:
        json.dump(creds, f, indent=4)

def load_database():
    if os.path.exists(DB_FILE):
        try:
            member_df = pd.read_excel(DB_FILE, sheet_name='Members')
            if not member_df.empty:
                member_df['ID'] = member_df['ID'].astype(int)
                member_df['Join Date'] = pd.to_datetime(member_df['Join Date']).dt.date
                member_df['Expiry Date'] = pd.to_datetime(member_df['Expiry Date']).dt.date
            else:
                member_df = pd.DataFrame(columns=['ID','Name','Phone','Membership Type','Join Date','Expiry Date'])
            log_df = pd.read_excel(DB_FILE, sheet_name='CheckIns')
            if not log_df.empty:
                log_df['CheckIn Time_dt'] = pd.to_datetime(log_df['CheckIn Time'].str.replace(' IST',''))
            else:
                log_df = pd.DataFrame(columns=['ID','Name','CheckIn Time','Staff User','CheckIn Time_dt'])
            return member_df, log_df
        except:
            pass
    member_df = pd.DataFrame(columns=['ID','Name','Phone','Membership Type','Join Date','Expiry Date'])
    log_df = pd.DataFrame(columns=['ID','Name','CheckIn Time','Staff User','CheckIn Time_dt'])
    save_database(member_df, log_df)
    return member_df, log_df

def save_database(member_df, log_df):
    with pd.ExcelWriter(DB_FILE, engine='openpyxl') as writer:
        member_df.to_excel(writer, sheet_name='Members', index=False)
        log_df.drop(columns=['CheckIn Time_dt'], errors='ignore').to_excel(writer, sheet_name='CheckIns', index=False)

# --- Staff Registration/Login ---
def staff_registration():
    st.subheader("Staff Registration")
    username = st.text_input("Username", key="reg_username")
    password = st.text_input("Password", type="password", key="reg_password")
    confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")

    if st.button("Register Staff", key="register_button"):
        if not username or not password:
            st.error("All fields required")
        elif password != confirm:
            st.error("Passwords do not match")
        elif username == OWNER_USERNAME:
            st.error("Reserved username")
        else:
            creds = load_staff_credentials()
            if username in creds:
                st.error("Username exists")
            else:
                creds[username] = hash_password(password)
                save_staff_credentials(creds)
                st.success(f"Staff '{username}' registered!")
                st.session_state['show_register'] = False

def login_page():
    st.title("Gym Membership System")
    st.subheader("Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        if username == OWNER_USERNAME and hash_password(password) == OWNER_PASSWORD_HASH:
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'owner'
            st.session_state['user'] = OWNER_USERNAME
            st.rerun()
        else:
            creds = load_staff_credentials()
            if username in creds and hash_password(password) == creds[username]:
                st.session_state['logged_in'] = True
                st.session_state['role'] = 'staff'
                st.session_state['user'] = username
                st.rerun()
            else:
                st.error("Invalid username/password")
    st.markdown("---")
    if st.button("Register Staff", key="show_reg_button"):
        st.session_state['show_register'] = True
    if st.session_state.get('show_register'):
        staff_registration()

# --- Sidebar ---
def sidebar():
    st.sidebar.title(f"User: {st.session_state.get('user','Guest')}")
    st.sidebar.markdown(f"Role: {st.session_state.get('role','N/A')}")
    if st.sidebar.button("Logout", key="logout_button"):
        st.session_state.clear()
        st.rerun()

# --- Pages ---
def check_in(member_df, log_df):
    st.header("Member Check-In")
    st.write("Current IST:", get_ist_time().strftime("%Y-%m-%d %H:%M:%S"))

    if not member_df.empty:
        member_df['ID'] = member_df['ID'].astype(int)

    member_id = int(st.number_input("Member ID", min_value=1, step=1, key="checkin_id"))

    if st.button("Record Entry", key="checkin_button"):
        member = member_df[member_df['ID'] == member_id]
        if member.empty:
            st.error("Member not found")
        else:
            name = member['Name'].iloc[0]
            expiry = member['Expiry Date'].iloc[0]
            today = get_ist_time().date()
            if expiry < today:
                st.error(f"{name} membership expired on {expiry}")
            else:
                time_str = get_ist_time().strftime("%Y-%m-%d %H:%M:%S IST")
                new_entry = pd.DataFrame([{
                    'ID': member_id,
                    'Name': name,
                    'CheckIn Time': time_str,
                    'Staff User': st.session_state['user'],
                    'CheckIn Time_dt': get_ist_time()
                }])
                log_df = pd.concat([log_df, new_entry], ignore_index=True)
                st.session_state['log_df'] = log_df
                save_database(member_df, log_df)
                st.success(f"Check-in recorded for {name} at {time_str}")

    st.subheader("Recent Check-ins")
    if not log_df.empty:
        st.dataframe(log_df.sort_values('CheckIn Time_dt', ascending=False).head(10)[['ID','Name','CheckIn Time','Staff User']])
    else:
        st.info("No check-ins yet.")

def member_management(member_df):
    st.header("Member Management")
    
    with st.expander("➕ Add Member"):
        next_id = int(member_df['ID'].max()) + 1 if not member_df.empty else 1

        name = st.text_input("Full Name", key="member_name")
        phone = st.text_input("Phone Number", key="member_phone")
        mtype = st.selectbox("Membership Type", ['Monthly', 'Quarterly', 'Annual', 'Trial'], key="member_type")
        join = st.date_input("Join Date", get_ist_time().date(), key="member_join")
        expiry = st.date_input("Expiry Date", join + datetime.timedelta(days=30), key="member_expiry")
        
        if st.button("Add Member", key="add_member_button"):
            if not name or not phone:
                st.error("All fields are required")
            elif expiry <= join:
                st.error("Expiry Date must be after Join Date")
            else:
                new_member = pd.DataFrame([{
                    'ID': next_id,
                    'Name': name,
                    'Phone': phone,
                    'Membership Type': mtype,
                    'Join Date': join,
                    'Expiry Date': expiry
                }])
                member_df = pd.concat([member_df, new_member], ignore_index=True)
                st.session_state['member_df'] = member_df
                save_database(member_df, st.session_state.get('log_df', pd.DataFrame()))
                st.success(f"Member '{name}' added with ID: {next_id}")
    
    st.subheader("All Members")
    if not member_df.empty:
        st.dataframe(member_df.sort_values('ID'))
    else:
        st.info("No members yet.")
    
    return member_df

def reminders(member_df):
    st.header("Membership Reminders")
    if st.session_state['role'] != 'owner':
        st.warning("Only owner can view reminders")
        return

    today = get_ist_time().date()
    df = member_df.copy()
    df['Days Left'] = (df['Expiry Date'] - today).apply(lambda x: x.days)

    st.subheader("Expired Memberships")
    expired = df[df['Days Left'] < 0]
    if not expired.empty:
        st.dataframe(expired)
    else:
        st.info("No expired memberships!")

    st.subheader("Expiring Within 30 Days")
    soon = df[(df['Days Left'] >= 0) & (df['Days Left'] <= 30)]
    if not soon.empty:
        st.dataframe(soon)
    else:
        st.info("No memberships expiring in next 30 days.")

# --- Main ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'show_register' not in st.session_state:
    st.session_state['show_register'] = False

if st.session_state['logged_in']:
    sidebar()
    if 'member_df' not in st.session_state or 'log_df' not in st.session_state:
        st.session_state['member_df'], st.session_state['log_df'] = load_database()
    
    pages = {
        "Check-In": check_in,
        "Member Management": member_management
    }
    if st.session_state['role'] == 'owner':
        pages["Membership Reminders"] = reminders

    choice = st.sidebar.radio("Navigate", list(pages.keys()))
    if choice == "Check-In":
        pages[choice](st.session_state['member_df'], st.session_state['log_df'])
    else:
        st.session_state['member_df'] = pages[choice](st.session_state['member_df'])
else:
    login_page()
