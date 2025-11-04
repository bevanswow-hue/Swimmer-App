import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json
from streamlit_option_menu import option_menu
import matplotlib.pyplot as plt
import altair as alt

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = "SwimmerLog"  # Replace with your Google Sheet name

def get_google_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(SPREADSHEET_NAME)
    return sheet

# Data model functions
def load_sessions():
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("Sessions")
    data = worksheet.get_all_records(expected_headers=[])
    return pd.DataFrame(data)

def save_session(session_data):
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("Sessions")
    worksheet.append_row(list(session_data.values()))

def load_targets():
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("Targets")
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_target(target_data):
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("Targets")
    worksheet.append_row(list(target_data.values()))

def load_css_tests():
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("CSSTests")
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_css_test(test_data):
    sheet = get_google_sheet()
    worksheet = sheet.worksheet("CSSTests")
    worksheet.append_row(list(test_data.values()))

# Main app
def main():
    st.set_page_config(page_title="Swimmer Log", layout="wide")

    # Sidebar navigation
    with st.sidebar:
        selected = option_menu(
            menu_title="Navigation",
            options=["Dashboard", "Log Session", "CSS Test", "Targets"],
            icons=["bar-chart", "pencil", "calculator", "target"],
            menu_icon="cast",
            default_index=0,
        )

    # Banner
    page_titles = {
        "Dashboard": "Dashboard",
        "Log Session": "Log Session",
        "CSS Test": "CSS Test",
        "Targets": "Targets"
    }
    st.markdown(f"""
    <div style="background-color: #2768F5; padding: 16px; text-align: center; font-size: 22px; font-weight: bold; color: white; margin-bottom: 16px; width: 100vw; margin-left: calc(-50vw + 50%);">
        Team Bon Dia Mate - {page_titles[selected]}
    </div>
    """, unsafe_allow_html=True)

    if selected == "Log Session":
        log_session_page()
    elif selected == "Dashboard":
        dashboard_page()
    elif selected == "CSS Test":
        css_test_page()
    elif selected == "Targets":
        targets_page()

def log_session_page():
    st.title("Log Swim Session")

    with st.form("session_form"):
        date_str = st.text_input("Date (dd-mmm-yy)", value=datetime.date.today().strftime("%d-%b-%y"))
        environment = st.selectbox("Environment", ["pool", "open_water"])
        distance_m = st.number_input("Distance (m)", min_value=0, step=100)
        total_time_min = st.number_input("Total Time (min)", min_value=0.0, step=0.1)
        moving_time_min = st.number_input("Moving Time (min, optional)", min_value=0.0, step=0.1, value=0.0)
        rest_estimate_min = st.number_input("Rest Estimate (min)", min_value=0.0, step=0.1)
        sets_text = st.text_area("Set Structure", placeholder="e.g., 8×100 @1:50, 4×50 kick")
        css_pace = st.text_input("CSS Pace (s/100m, optional)", "")
        avg_pace = st.text_input("Average Pace (s/100m)", "")
        rpe = st.slider("Intensity (RPE 1-10)", 1, 10, 5)
        notes = st.text_area("Notes", placeholder="How you felt, niggles, water temp")
        team = st.text_input("Team", "")
        swimmer = st.selectbox("Swimmer", ["BVH", "AVH", "AA", "FGQ"])

        submitted = st.form_submit_button("Submit")

        if submitted:
            try:
                date = datetime.datetime.strptime(date_str, "%d-%b-%y").date()
            except ValueError:
                st.error("Invalid date format. Please use dd-mmm-yy (e.g., 04-Nov-25)")
                return
            session_data = {
                "date": str(date),
                "environment": environment,
                "distance_m": distance_m,
                "total_time_min": total_time_min,
                "moving_time_min": moving_time_min if moving_time_min > 0 else None,
                "rest_estimate_min": rest_estimate_min,
                "sets_text": sets_text,
                "css_pace": css_pace,
                "avg_pace": avg_pace,
                "rpe": rpe,
                "notes": notes,
                "team": team,
                "swimmer": swimmer
            }
            save_session(session_data)
            st.success("Session logged successfully!")

def dashboard_page():
    st.title("Dashboard")

    sessions_df = load_sessions()
    if sessions_df.empty:
        st.write("No sessions logged yet.")
        return

    df = sessions_df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['distance_km'] = df['distance_m'] / 1000
    df['load'] = df['distance_km'] * df['rpe']

    # Weekly aggregations by swimmer
    df['week'] = df['date'].dt.to_period('W').apply(lambda r: r.start_time)
    weekly_df = df.groupby(['week', 'swimmer']).agg({
        'distance_km': 'sum',
        'load': 'sum',
        'rpe': ['mean', 'std']
    }).reset_index()
    weekly_df.columns = ['week', 'swimmer', 'total_distance_km', 'total_load', 'mean_rpe', 'std_rpe']
    weekly_df['monotony'] = weekly_df['mean_rpe'] / weekly_df['std_rpe'].replace(0, 1)  # Avoid div by zero
    weekly_df['strain'] = weekly_df['monotony'] * weekly_df['total_load']

    # Current week data
    current_week = pd.Timestamp.now().to_period('W').start_time
    current_week_df = weekly_df[weekly_df['week'] == current_week]

    # Last week data
    last_week = current_week - pd.Timedelta(days=7)
    last_week_df = weekly_df[weekly_df['week'] == last_week]

    # Create three columns for the summary section
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div style="background-color: #00008B; color: white; padding: 10px;"><strong>This Week\'s KM by Swimmer</strong></div>', unsafe_allow_html=True)
        if not current_week_df.empty:
            pie_data = current_week_df.set_index('swimmer')['total_distance_km']
            st.bar_chart(pie_data, height=200)  # Using bar chart as pie charts aren't directly supported
        else:
            st.write("No data for this week yet.")

    with col2:
        st.markdown('<div style="background-color: #00008B; color: white; padding: 10px;"><strong>Last Week\'s KM by Swimmer</strong></div>', unsafe_allow_html=True)
        if not last_week_df.empty:
            # Create pie chart data
            pie_values = last_week_df['total_distance_km'].values
            pie_labels = last_week_df['swimmer'].values
            colors = ['darkgreen', 'darkred', 'darkblue', 'pink']
            fig, ax = plt.subplots(figsize=(2.8, 2.8))
            wedges, texts, autotexts = ax.pie(pie_values, autopct=lambda pct: f'{pct/100.*sum(pie_values):.1f}km', startangle=90, colors=colors, textprops={'color':'white'})
            ax.axis('equal')
            ax.legend(wedges, pie_labels, title="Swimmers", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
            st.pyplot(fig)
        else:
            st.write("No data for last week.")

    with col3:
        st.markdown('<div style="background-color: #00008B; color: white; padding: 10px;"><strong>Next Training Session</strong></div>', unsafe_allow_html=True)
        # Get next training session
        training_schedule = {
            0: "Monday - All swimmers, 5:45pm @ Claremont Pool",  # Monday
            1: "Tuesday - No training",  # Tuesday
            2: "Wednesday - Masters session, 6:00pm @ Scarborough Pool",  # Wednesday
            3: "Thursday - No training",  # Thursday
            4: "Friday - Technique session, 5:30pm @ Bold Park",  # Friday
            5: "Saturday - Long swim, 7:00am @ Claremont Pool",  # Saturday
            6: "Sunday - Recovery swim, 8:00am @ Claremont Pool"  # Sunday
        }

        today = datetime.date.today()
        current_day = today.weekday()  # 0=Monday, 6=Sunday

        # Find next training day
        next_day = current_day
        days_ahead = 0
        while days_ahead < 7:
            next_day = (current_day + days_ahead) % 7
            if "No training" not in training_schedule[next_day]:
                break
            days_ahead += 1

        next_date = today + datetime.timedelta(days=days_ahead)
        day_name = next_date.strftime("%A")
        session_info = training_schedule[next_day].replace("Monday", day_name).replace("Tuesday", day_name).replace("Wednesday", day_name).replace("Thursday", day_name).replace("Friday", day_name).replace("Saturday", day_name).replace("Sunday", day_name)

        st.write(f"{next_date.strftime('%a %d-%b')}")
        st.write(session_info)

    # Pivot for clustered bar chart
    distance_pivot = weekly_df.pivot(index='week', columns='swimmer', values='total_distance_km').fillna(0)

    # Charts
    st.subheader("Weekly Distance by Swimmer")
    # Create custom stacked bar chart with wider bars
    melted_df = distance_pivot.reset_index().melt(id_vars='week', var_name='swimmer', value_name='distance')
    melted_df['week'] = melted_df['week'].dt.strftime('%Y-%m-%d')
    melted_df = melted_df.sort_values('week')
    chart = alt.Chart(melted_df).mark_bar(size=60).encode(
        x=alt.X('week:O', title='Week'),
        y=alt.Y('distance:Q', title='Distance (KM)', stack='zero'),
        color='swimmer:N'
    ).properties(
        width=600,
        height=400
    )
    st.altair_chart(chart)

    st.subheader("Training Load")
    st.line_chart(weekly_df.set_index('week')[['total_load', 'monotony', 'strain']])

    # Last 10 sessions
    st.subheader("Last 10 Sessions")
    st.dataframe(df.sort_values('date', ascending=False).head(10))

def css_test_page():
    st.title("CSS Test Helper")

    with st.form("css_form"):
        date = st.date_input("Date", datetime.date.today())
        swimmer = st.text_input("Swimmer", "")
        time_200_s = st.number_input("200m Time (s)", min_value=0.0, step=0.1)
        time_400_s = st.number_input("400m Time (s)", min_value=0.0, step=0.1)

        submitted = st.form_submit_button("Calculate CSS")

        if submitted:
            if time_200_s > 0 and time_400_s > 0:
                css_pace = (time_400_s - time_200_s) / 2
                test_data = {
                    "date": str(date),
                    "swimmer": swimmer,
                    "time_200_s": time_200_s,
                    "time_400_s": time_400_s,
                    "css_s_per_100": css_pace
                }
                save_css_test(test_data)
                st.success(f"CSS Pace: {css_pace:.2f} s/100m")
            else:
                st.error("Please enter valid times.")

def targets_page():
    st.title("Targets")

    with st.form("target_form"):
        week_start = st.date_input("Week Start (Monday)", datetime.date.today())
        swimmer = st.text_input("Swimmer", "")
        km_target = st.number_input("KM Target", min_value=0.0, step=0.1)

        submitted = st.form_submit_button("Set Target")

        if submitted:
            target_data = {
                "week_start": str(week_start),
                "swimmer": swimmer,
                "km_target": km_target
            }
            save_target(target_data)
            st.success("Target set!")

if __name__ == "__main__":
    main()