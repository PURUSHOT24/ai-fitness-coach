
import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import secrets
from datetime import date
from google import genai

# --------------------------------------------------
# 1. APP CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Fitness Coach",
    page_icon="💪",
    layout="wide"
)

DB_FILE = "fitness_app.db"


# --------------------------------------------------
# 2. DATABASE SETUP (SQLite for the first version)
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                goal TEXT,
                duration INTEGER,
                plan TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS workout_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                task_date TEXT NOT NULL,
                exercise TEXT NOT NULL,
                completed INTEGER DEFAULT 0
            )
        """)


initialize_db()


# --------------------------------------------------
# 3. SECURE PASSWORD HELPERS
# --------------------------------------------------

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200000
    ).hex()


def register_user(username, password):
    username = username.strip().lower()

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, salt, password_hash) "
                "VALUES (?, ?, ?)",
                (username, salt, password_hash)
            )
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "This username already exists."


def verify_user(username, password):
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip().lower(),)
        ).fetchone()

    if not user:
        return False

    return secrets.compare_digest(
        hash_password(password, user["salt"]),
        user["password_hash"]
    )


# --------------------------------------------------
# 4. GEMINI AI CONFIGURATION
# --------------------------------------------------

try:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    api_key = ""

client = genai.Client(api_key=api_key) if api_key else None


# --------------------------------------------------
# 5. LOGIN / REGISTRATION
# --------------------------------------------------

if "username" not in st.session_state:
    st.session_state.username = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if not st.session_state.username:

    st.title("💪 AI Fitness Coach")
    st.caption(
        "Your personal AI-powered fitness and nutrition platform"
    )

    login_tab, register_tab = st.tabs(
        ["🔐 Login", "📝 Register"]
    )

    with login_tab:
        st.subheader("Welcome Back")

        with st.form("login_form"):
            login_username = st.text_input("Username")
            login_password = st.text_input(
                "Password", type="password"
            )
            login_button = st.form_submit_button(
                "Login", type="primary", use_container_width=True
            )

        if login_button:
            if verify_user(login_username, login_password):
                st.session_state.username = (
                    login_username.strip().lower()
                )
                st.session_state.chat_history = []
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with register_tab:
        st.subheader("Create Your Account")

        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input(
                "Create password (minimum 8 characters)",
                type="password"
            )
            confirm_password = st.text_input(
                "Confirm password", type="password"
            )

            register_button = st.form_submit_button(
                "Create Account",
                type="primary",
                use_container_width=True
            )

        if register_button:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                success, message = register_user(
                    new_username, new_password
                )

                if success:
                    st.success(message)
                    st.info("Please go to the Login tab to sign in.")
                else:
                    st.error(message)

    st.stop()


# --------------------------------------------------
# 6. MAIN APP NAVIGATION
# --------------------------------------------------

username = st.session_state.username

with st.sidebar:
    st.title("💪 Fitness Coach")
    st.caption(f"Logged in as: {username}")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Generate AI Plan",
            "Track Progress",
            "Workout Checklist",
            "AI Coach"
        ]
    )

    st.divider()

    if st.button("Logout", use_container_width=True):
        st.session_state.username = None
        st.session_state.chat_history = []
        st.rerun()


# --------------------------------------------------
# 7. DASHBOARD
# --------------------------------------------------


if page == "Dashboard":

    st.title("💪 Fitness Dashboard")
    st.write(f"Welcome back, **{username}**! 👋")
    st.caption("Your personal fitness journey at a glance.")

    # Load user's progress and AI plan count
    with get_db() as conn:
        progress_df = pd.read_sql_query(
            """
            SELECT record_date, steps, workout_minutes, weight
            FROM progress
            WHERE username = ?
            ORDER BY record_date, id
            """,
            conn,
            params=(username,)
        )

        plan_count = conn.execute(
            "SELECT COUNT(*) FROM plans WHERE username = ?",
            (username,)
        ).fetchone()[0]

        latest_plan = conn.execute(
            """
            SELECT goal, duration, plan, created_at
            FROM plans
            WHERE username = ?
            ORDER BY id DESC LIMIT 1
            """,
            (username,)
        ).fetchone()

    # Calculate dashboard values
    latest_weight = 0
    if not progress_df.empty:
        weights = pd.to_numeric(
            progress_df["weight"], errors="coerce"
        ).dropna()

        if not weights.empty:
            latest_weight = float(weights.iloc[-1])

    total_workouts = (
        int((progress_df["workout_minutes"] > 0).sum())
        if not progress_df.empty else 0
    )

    total_steps = (
        int(progress_df["steps"].fillna(0).sum())
        if not progress_df.empty else 0
    )

    # Summary cards
    st.subheader("📊 Your Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🤖 AI Plans", plan_count)
    col2.metric("🏋️ Workouts", total_workouts)
    col3.metric(
        "⚖️ Latest Weight",
        f"{latest_weight:.1f} kg"
        if latest_weight > 0 else "Not recorded"
    )
    col4.metric("🚶 Total Steps", f"{total_steps:,}")

    st.divider()

    # Progress charts
    st.subheader("📈 Your Progress")

    if not progress_df.empty:
        chart_df = progress_df.copy()
        chart_df["record_date"] = pd.to_datetime(
            chart_df["record_date"], errors="coerce"
        )

        chart_df["steps"] = pd.to_numeric(
            chart_df["steps"], errors="coerce"
        )
        chart_df["workout_minutes"] = pd.to_numeric(
            chart_df["workout_minutes"], errors="coerce"
        )
        chart_df["weight"] = pd.to_numeric(
            chart_df["weight"], errors="coerce"
        )

        left, right = st.columns(2)

        with left:
            st.markdown("#### ⚖️ Weight History")
            weight_df = chart_df.dropna(
                subset=["record_date", "weight"]
            )
            if not weight_df.empty:
                st.line_chart(
                    weight_df.set_index("record_date")["weight"]
                )
            else:
                st.info("Add weight records to see your chart.")

        with right:
            st.markdown("#### 🏃 Daily Activity")
            activity_df = chart_df.dropna(
                subset=["record_date", "steps"]
            )
            if not activity_df.empty:
                st.bar_chart(
                    activity_df.set_index("record_date")["steps"]
                )
            else:
                st.info("Add step records to see your chart.")
    else:
        st.info(
            "👋 Your journey starts here! "
            "Open Track Progress to add your first record."
        )

    st.divider()

    # Latest personalized plan
    st.subheader("✨ Your Personalized AI Plan")

    if latest_plan:
        st.markdown(f"**Goal:** {latest_plan['goal']}")
        st.markdown(
            f"**Plan duration:** {latest_plan['duration']} days"
        )

        with st.expander("📋 View your latest fitness plan"):
            st.markdown(latest_plan["plan"])
    else:
        st.info(
            "You haven't generated a plan yet. "
            "Open Generate AI Plan to create your first plan."
        )

# --------------------------------------------------
# 8. AI FITNESS PLAN GENERATOR
# --------------------------------------------------

elif page == "Generate AI Plan":

    st.title("✨ Personalized Fitness Plan")
    st.write(
        "Generate a workout and Indian meal plan "
        "based on your goals and preferences."
    )

    with st.form("fitness_form"):

        goal = st.selectbox(
            "Fitness Goal",
            ["Lose Weight", "Gain Muscle", "Maintain Weight",
             "Improve Endurance"]
        )

        duration = st.selectbox(
            "Plan Duration",
            [7, 15, 30, 60, 90],
            index=2,
            format_func=lambda days: f"{days} Days"
        )

        col1, col2 = st.columns(2)

        with col1:
            age = st.number_input(
                "Age", min_value=18, max_value=100, value=20
            )
            weight = st.number_input(
                "Weight (kg)", min_value=20.0,
                max_value=300.0, value=60.0
            )
            height = st.number_input(
                "Height (cm)", min_value=100.0,
                max_value=250.0, value=170.0
            )

        with col2:
            activity = st.selectbox(
                "Activity Level",
                ["Beginner / Low Activity",
                 "Moderate Activity", "Highly Active"]
            )

            food = st.selectbox(
                "Food Preference",
                ["South Indian Vegetarian",
                 "North Indian Vegetarian",
                 "Vegetarian",
                 "Non-Vegetarian",
                 "Vegan"]
            )

            equipment = st.selectbox(
                "Available Equipment",
                ["No Equipment", "Dumbbells", "Full Gym"]
            )

        budget = st.selectbox(
            "Food Budget",
            ["Budget-friendly", "Moderate", "Flexible"]
        )

        health_notes = st.text_area(
            "Optional limitations or food allergies",
            placeholder=(
                "For example: knee discomfort, peanut allergy. "
                "Do not enter private medical records."
            )
        )

        generate_button = st.form_submit_button(
            "Generate My Workout + Diet Plan",
            type="primary",
            use_container_width=True
        )

    if generate_button:

        if not client:
            st.error(
                "Gemini API key is missing. Check your "
                ".streamlit/secrets.toml configuration."
            )
        else:
            prompt = f"""
You are a careful fitness and nutrition coach familiar
with Indian food habits and beginner-friendly exercise.

USER DETAILS:
Goal: {goal}
Duration: {duration} days
Age: {age}
Weight: {weight} kg
Height: {height} cm
Activity level: {activity}
Food preference: {food}
Equipment: {equipment}
Food budget: {budget}
User-provided limitations/allergies: {health_notes or "Not provided"}

Create a practical, personalized plan.

WORKOUT:
- Provide a seven-day schedule with exercise names,
  sets, repetitions or duration, and rest days.
- Adapt exercises to the selected equipment and fitness level.
- Include warm-up, recovery and gradual progression.
- Offer safe alternatives for any stated limitation.
- Do not encourage exercising through pain.

INDIAN MEAL PLAN:
- Provide breakfast, lunch, dinner and snacks for seven days.
- Use foods appropriate to the selected food preference.
- Consider idli, dosa, sambar, rice, rasam, curd, upma,
  sundal, roti, dal, vegetables, chickpeas, paneer,
  milk, eggs, fish or chicken when suitable.
- Match the selected regional preference where practical.
- Respect allergies and avoid recommending foods that
  conflict with stated restrictions.
- Give approximate household portions and affordable options.
- Include a variety of protein sources.

PERSONALIZATION:
- Explain how to repeat or adapt the weekly plan over
  the requested {duration}-day duration.
- Include a simple weekly tracker for workouts and weight.
- Do not guarantee weight loss or muscle gain.
- Avoid crash diets, starvation, and excessive exercise.
- Do not invent precise calorie requirements.
- Keep the advice practical and use simple English.
- Mention that individual needs vary and this is general
  wellness guidance, not medical advice.

Format the answer with clear headings and tables where useful.
"""

            try:
                with st.spinner(
                    "Creating your personalized Indian fitness plan..."
                ):
                    response = client.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=prompt,
                        config={
                            "http_options": {"timeout": 60000}
                        }
                    )

                plan_text = response.text or (
                    "No plan was returned. Please try again."
                )

                with get_db() as conn:
                    conn.execute(
                        """
                        INSERT INTO plans
                        (username, goal, duration, plan)
                        VALUES (?, ?, ?, ?)
                        """,
                        (username, goal, duration, plan_text)
                    )

                st.success("Your fitness plan has been saved!")
                st.subheader("🏋️ Your Workout and Diet Plan")
                st.markdown(plan_text)

            except Exception as e:
                st.error(f"Could not generate your plan: {e}")


# --------------------------------------------------
# 9. FITNESS PROGRESS TRACKER
# --------------------------------------------------

elif page == "Track Progress":

    st.title("📊 Track Your Fitness Progress")
    st.write(
        "Record your daily activity and monitor your progress."
    )

    with st.form("progress_form"):

        record_date = st.date_input(
            "Record Date", value=date.today()
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            steps = st.number_input(
                "Steps Walked", min_value=0,
                max_value=100000, value=5000, step=500
            )

        with col2:
            workout_minutes = st.number_input(
                "Workout Minutes", min_value=0,
                max_value=600, value=30
            )

        with col3:
            weight = st.number_input(
                "Weight (kg)", min_value=20.0,
                max_value=300.0, value=60.0, step=0.5
            )

        notes = st.text_input(
            "Notes (optional)",
            placeholder="For example: completed today's workout"
        )

        save_button = st.form_submit_button(
            "Save Progress", type="primary"
        )

    if save_button:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO progress
                (username, record_date, steps,
                 workout_minutes, weight, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username, str(record_date), steps,
                    workout_minutes, weight, notes
                )
            )

        st.success("Your progress has been saved!")
        st.rerun()

    with get_db() as conn:
        history = pd.read_sql_query(
            """
            SELECT record_date AS Date, steps AS Steps,
                   workout_minutes AS Workout_Minutes,
                   weight AS Weight_kg, notes AS Notes
            FROM progress
            WHERE username = ?
            ORDER BY record_date DESC, id DESC
            """,
            conn,
            params=(username,)
        )

    st.subheader("📋 Your Progress History")

    if not history.empty:
        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No progress records yet. Save your first record above.")


# --------------------------------------------------
# 10. AI CHATBOT
# Existing Gemini chatbot functionality preserved
# --------------------------------------------------

elif page == "Workout Checklist":

    st.title("🏋️ Daily Workout Checklist")
    st.write("Add exercises and tick them off as you complete them.")

    task_date = st.date_input(
        "Workout date", value=date.today(),
        key="checklist_date"
    )

    with st.form("add_workout_task"):
        exercise = st.text_input(
            "Exercise name",
            placeholder="e.g. Push-ups, Squats, Walking"
        )
        add_task = st.form_submit_button("➕ Add Exercise")

    if add_task:
        if exercise.strip():
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO workout_tasks
                    (username, task_date, exercise, completed)
                    VALUES (?, ?, ?, 0)
                    """,
                    (username, str(task_date), exercise.strip())
                )
            st.success("Exercise added!")
            st.rerun()
        else:
            st.warning("Please enter an exercise name.")

    with get_db() as conn:
        tasks = conn.execute(
            """
            SELECT id, exercise, completed
            FROM workout_tasks
            WHERE username = ? AND task_date = ?
            ORDER BY id
            """,
            (username, str(task_date))
        ).fetchall()

    st.subheader("📋 Today's Exercises")

    if tasks:
        completed_count = sum(int(task["completed"]) for task in tasks)
        total_count = len(tasks)

        st.progress(completed_count / total_count)
        st.caption(
            f"{completed_count} of {total_count} exercises completed"
        )

        for task in tasks:
            is_completed = st.checkbox(
                task["exercise"],
                value=bool(task["completed"]),
                key=f"workout_task_{task['id']}"
            )

            if is_completed != bool(task["completed"]):
                with get_db() as conn:
                    conn.execute(
                        """
                        UPDATE workout_tasks
                        SET completed = ?
                        WHERE id = ? AND username = ?
                        """,
                        (int(is_completed), task["id"], username)
                    )
                st.rerun()
    else:
        st.info("No exercises added for this date yet.")

elif page == "AI Coach":

    st.title("🤖 AI Fitness Coach")
    st.caption(
        "Ask questions about fitness, food, programming, "
        "or other topics."
    )

    if not client:
        st.warning("Please configure your Gemini API key.")
    else:
        # Display previous messages
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        user_question = st.chat_input("Ask me anything...")

        if user_question:
            with st.chat_message("user"):
                st.write(user_question)

            # Prepare recent conversation context
            history = "\n".join(
                f"{message['role']}: {message['content']}"
                for message in st.session_state.chat_history[-6:]
            )

            try:
                with st.spinner("AI is thinking..."):
                    response = client.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=(
                            "You are an intelligent, helpful AI assistant. "
                            "Answer questions on any topic, not just fitness. "
                            "Understand the user's intent and answer directly. "
                            "Be accurate, logical, and honest when uncertain. "
                            "Use simple English and examples when helpful. "
                            "For coding questions, provide correct, runnable code. "
                            "For follow-up questions, use the conversation history. "
                            "Keep simple answers short and complex answers detailed.\n\n"
                            f"Conversation history:\n{history}\n\n"
                            f"User question: {user_question}"
                        ),
                        config={
                            "http_options": {"timeout": 60000}
                        }
                    )

                answer = response.text or "Please try asking again."

                st.session_state.chat_history.append({
                    "role": "user",
                    "content": user_question
                })
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer
                })

                with st.chat_message("assistant"):
                    st.write(answer)

            except Exception as e:
                st.error(f"AI error: {e}")
