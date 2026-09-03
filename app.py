from flask import Flask, render_template, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)

# Secret key for sessions
app.secret_key = "datawise_secret_key_2026"

# ============================================================
# DATABASE FILE
# ============================================================

DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "datawise.db"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    # USERS
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # PRIVACY SCORE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS privacy_scores (
            user_id INTEGER PRIMARY KEY,
            score INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # COMPLETED ACTIVITIES
    conn.execute("""
        CREATE TABLE IF NOT EXISTS completed_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity TEXT NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, activity),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    session.clear()

    return render_template("index.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password or not confirm_password:

            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(url_for("register"))

        if len(username) < 3:

            flash(
                "Username must contain at least 3 characters.",
                "error"
            )

            return redirect(url_for("register"))

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return redirect(url_for("register"))

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:

            cursor = conn.execute(
                """
                INSERT INTO users (username, password)
                VALUES (?, ?)
                """,
                (username, hashed_password)
            )

            user_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO privacy_scores (user_id, score)
                VALUES (?, ?)
                """,
                (user_id, 0)
            )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            flash(
                "Username already exists. Please choose another username.",
                "error"
            )

            return redirect(url_for("register"))

        conn.close()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:

            flash(
                "Please enter your username and password.",
                "error"
            )

            return redirect(url_for("login"))

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            conn = get_db()

            score = conn.execute(
                """
                SELECT *
                FROM privacy_scores
                WHERE user_id = ?
                """,
                (user["id"],)
            ).fetchone()

            if score is None:

                conn.execute(
                    """
                    INSERT INTO privacy_scores
                    (user_id, score)
                    VALUES (?, ?)
                    """,
                    (user["id"], 0)
                )

                conn.commit()

            conn.close()

            return redirect(url_for("dashboard"))

        flash(
            "Invalid username or password.",
            "error"
        )

        return redirect(url_for("login"))

    return render_template("login.html")


# ============================================================
# HELPER - GET SCORE
# ============================================================

def get_user_score(user_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT score
        FROM privacy_scores
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    if row:

        return max(
            0,
            min(100, row["score"])
        )

    return 0


# ============================================================
# HELPER - CHECK ACTIVITY
# ============================================================

def activity_completed(user_id, activity):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM completed_activities
        WHERE user_id = ?
        AND activity = ?
        """,
        (user_id, activity)
    ).fetchone()

    conn.close()

    return row is not None


# ============================================================
# HELPER - COMPLETE ACTIVITY
# ============================================================

def complete_activity(user_id, activity, points):

    conn = get_db()

    existing = conn.execute(
        """
        SELECT *
        FROM completed_activities
        WHERE user_id = ?
        AND activity = ?
        """,
        (user_id, activity)
    ).fetchone()

    if existing:

        conn.close()

        return False

    conn.execute(
        """
        INSERT INTO completed_activities
        (user_id, activity)
        VALUES (?, ?)
        """,
        (user_id, activity)
    )

    conn.execute(
        """
        UPDATE privacy_scores
        SET score = MIN(100, score + ?)
        WHERE user_id = ?
        """,
        (points, user_id)
    )

    conn.commit()
    conn.close()

    return True


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    username = session.get("username")
    user_id = session.get("user_id")

    privacy_score = get_user_score(user_id)

    dashboard_html = """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>DataWise Dashboard</title>

<style>

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    background: #f7faf9;
    color: #17221e;
    line-height: 1.6;
}

a {
    text-decoration: none;
}

.navbar {
    width: 100%;
    min-height: 72px;
    padding: 0 7%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: white;
    border-bottom: 1px solid #e5ebe8;
}

.logo {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #17221e;
}

.logo span {
    color: #15966f;
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 25px;
}

.nav-links a {
    color: #26332e;
    font-weight: 600;
}

.nav-links a:hover {
    color: #15966f;
}

.logout-btn {
    padding: 10px 20px;
    border-radius: 8px;
    background: #15966f;
    color: white !important;
}

.dashboard-hero {
    padding: 75px 7%;
    background: linear-gradient(
        135deg,
        #effaf5,
        #ffffff
    );
}

.dashboard-hero-content {
    max-width: 850px;
    margin: auto;
    text-align: center;
}

.small-title {
    color: #15966f;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 2px;
    margin-bottom: 15px;
}

.dashboard-hero h1 {
    font-size: 48px;
    line-height: 1.2;
    margin-bottom: 20px;
}

.dashboard-hero h1 span {
    color: #15966f;
}

.dashboard-hero-text {
    max-width: 700px;
    margin: auto;
    font-size: 18px;
    color: #596761;
}

.dashboard-section {
    padding: 75px 7%;
    background: white;
}

.section-heading {
    max-width: 700px;
    margin: 0 auto 45px;
    text-align: center;
}

.section-heading h2 {
    font-size: 36px;
    margin-bottom: 12px;
}

.section-heading p {
    color: #66736e;
    font-size: 17px;
}

.score-card {
    max-width: 900px;
    margin: 0 auto 50px;
    padding: 35px;
    background: #fbfdfc;
    border: 1px solid #e1ebe6;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
}

.score-content {
    flex: 1;
}

.score-content h3 {
    font-size: 24px;
    margin-bottom: 8px;
}

.score-content p {
    color: #66736e;
}

.score-progress {
    width: 100%;
    max-width: 450px;
    height: 9px;
    margin-top: 18px;
    background: #dfeae5;
    border-radius: 20px;
    overflow: hidden;
}

.score-progress-bar {
    height: 100%;
    width: {{ privacy_score }}%;
    background: #15966f;
    border-radius: 20px;
    transition: width 0.5s ease;
}

.score-circle {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    border: 9px solid #15966f;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.score-circle strong {
    font-size: 30px;
    color: #15966f;
}

.dashboard-grid {
    max-width: 1150px;
    margin: auto;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 25px;
}

.dashboard-card {
    padding: 30px;
    background: #fbfdfc;
    border: 1px solid #e3ebe7;
    border-radius: 15px;
    transition: 0.2s;
    display: flex;
    flex-direction: column;
}

.dashboard-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 30px rgba(20, 50, 40, 0.08);
    border-color: #cfe4db;
}

.dashboard-icon {
    width: 58px;
    height: 58px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #effaf5;
    border-radius: 14px;
    font-size: 28px;
    margin-bottom: 18px;
}

.dashboard-card h3 {
    font-size: 21px;
    margin-bottom: 10px;
}

.dashboard-card p {
    color: #66736e;
    margin-bottom: 22px;
    flex-grow: 1;
}

.card-btn {
    display: inline-block;
    width: 100%;
    padding: 11px 18px;
    text-align: center;
    border-radius: 8px;
    background: white;
    color: #15966f;
    border: 1px solid #15966f;
    font-weight: 700;
    cursor: pointer;
}

.card-btn:hover {
    background: #effaf5;
}

.tip-section {
    padding: 20px 7% 75px;
    background: white;
}

.tip-box {
    max-width: 900px;
    margin: auto;
    padding: 28px 32px;
    display: flex;
    align-items: flex-start;
    gap: 20px;
    background: #effaf5;
    border: 1px solid #d5ebe2;
    border-radius: 15px;
}

.tip-icon {
    font-size: 32px;
}

.tip-box h2 {
    font-size: 22px;
    margin-bottom: 5px;
}

.tip-box p {
    color: #596761;
}

footer {
    padding: 40px 7%;
    text-align: center;
    background: #17221e;
    color: white;
}

footer .logo {
    color: white;
}

footer p {
    color: #b8c4bf;
    margin-top: 8px;
}

.copyright {
    font-size: 13px;
}

@media (max-width: 900px) {

    .dashboard-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .dashboard-hero h1 {
        font-size: 40px;
    }

}

@media (max-width: 650px) {

    .navbar {
        padding: 15px 5%;
        flex-direction: column;
        gap: 15px;
    }

    .nav-links {
        gap: 12px;
        flex-wrap: wrap;
        justify-content: center;
    }

    .dashboard-hero {
        padding: 60px 6%;
    }

    .dashboard-hero h1 {
        font-size: 32px;
    }

    .dashboard-hero-text {
        font-size: 16px;
    }

    .dashboard-section {
        padding: 55px 6%;
    }

    .section-heading h2 {
        font-size: 30px;
    }

    .score-card {
        flex-direction: column;
        text-align: center;
        padding: 28px 22px;
    }

    .score-progress {
        margin-left: auto;
        margin-right: auto;
    }

    .dashboard-grid {
        grid-template-columns: 1fr;
    }

    .dashboard-card {
        padding: 25px;
    }

    .tip-section {
        padding: 10px 6% 55px;
    }

    .tip-box {
        flex-direction: column;
        padding: 22px;
        gap: 10px;
    }

}

@media (max-width: 450px) {

    .logo {
        font-size: 21px;
    }

    .nav-links {
        font-size: 14px;
    }

    .dashboard-hero h1 {
        font-size: 29px;
    }

    .score-circle {
        width: 105px;
        height: 105px;
    }

    .score-circle strong {
        font-size: 27px;
    }

}

</style>

</head>

<body>

<nav class="navbar">

<a href="{{ url_for('index') }}"
   class="logo">
Data<span>Wise</span>
</a>

<div class="nav-links">

<a href="{{ url_for('index') }}">
Home
</a>

<a href="{{ url_for('logout') }}"
   class="logout-btn">
Logout
</a>

</div>

</nav>

<section class="dashboard-hero">

<div class="dashboard-hero-content">

<p class="small-title">
DATAWISE DASHBOARD
</p>

<h1>
Welcome,
<span>{{ username }}</span> 👋
</h1>

<p class="dashboard-hero-text">
Take control of your digital privacy.
Learn how free apps use your data and
understand the real value of your personal
information.
</p>

</div>

</section>

<section class="dashboard-section">

<div class="section-heading">

<h2>
Your Data Awareness
</h2>

<p>
Explore DataWise to understand how your
personal data is collected, used and shared.
</p>

</div>

<div class="score-card">

<div class="score-content">

<h3>
🔐 Privacy Awareness Score
</h3>

<p>
Your score shows how much of the DataWise
awareness journey you have completed.
Complete activities to improve your score.
</p>

<div class="score-progress">

<div class="score-progress-bar"></div>

</div>

</div>

<div class="score-circle">

<strong>
{{ privacy_score }}%
</strong>

</div>

</div>

<div class="dashboard-grid">

<div class="dashboard-card">

<div class="dashboard-icon">
📱
</div>

<h3>
Free Apps & Your Data
</h3>

<p>
Learn why many apps are free and how
personal data can become part of the
digital business model.
</p>

<a href="{{ url_for('free_apps') }}"
   class="card-btn">
Explore
</a>

</div>

<div class="dashboard-card">

<div class="dashboard-icon">
🔍
</div>

<h3>
What Data Do Apps Collect?
</h3>

<p>
Discover the different types of personal
information that apps and online services
may collect.
</p>

<a href="{{ url_for('data_collection') }}"
   class="card-btn">
Explore
</a>

</div>

<div class="dashboard-card">

<div class="dashboard-icon">
💰
</div>

<h3>
Value of Your Data
</h3>

<p>
Understand why personal data has value
and how businesses may use information
about their users.
</p>

<a href="{{ url_for('data_value') }}"
   class="card-btn">
Explore
</a>

</div>

<div class="dashboard-card">

<div class="dashboard-icon">
🛡️
</div>

<h3>
Protect Your Privacy
</h3>

<p>
Learn simple and practical habits that
can help you make safer decisions when
using digital services.
</p>

<a href="{{ url_for('protect_privacy') }}"
   class="card-btn">
Learn
</a>

</div>

<div class="dashboard-card">

<div class="dashboard-icon">
🍪
</div>

<h3>
Cookies & Tracking
</h3>

<p>
Understand cookies, tracking technologies
and how online activity can be used to
understand user behaviour.
</p>

<a href="{{ url_for('cookies_tracking') }}"
   class="card-btn">
Learn
</a>

</div>

<div class="dashboard-card">

<div class="dashboard-icon">
🧠
</div>

<h3>
Test Your Knowledge
</h3>

<p>
Test your understanding of personal data,
privacy and the hidden cost of free
digital services.
</p>

<a href="{{ url_for('quiz') }}"
   class="card-btn">
Start Quiz
</a>

</div>

</div>

</section>

<section class="tip-section">

<div class="tip-box">

<div class="tip-icon">
💡
</div>

<div>

<h2>
DataWise Tip
</h2>

<p>
Your personal data has value.
Think before you share it and check
what information an app requests before
giving permission.
</p>

</div>

</div>

</section>

<footer>

<div class="logo">
Data<span>Wise</span>
</div>

<p>
Understand Your Data. Protect Your Privacy.
</p>

<p class="copyright">
© 2026 DataWise. All rights reserved.
</p>

</footer>

</body>

</html>
"""

    return render_template_string(
        dashboard_html,
        username=username,
        privacy_score=privacy_score
    )


# ============================================================
# COMMON CSS FOR LEARNING PAGES
# ============================================================

learning_css = """
<style>

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    background: #f7faf9;
    color: #17221e;
    line-height: 1.6;
}

.page {
    max-width: 900px;
    margin: auto;
    padding: 35px 20px 60px;
}

.back {
    color: #15966f;
    font-weight: 700;
    text-decoration: none;
}

.card {
    margin-top: 25px;
    background: white;
    padding: 35px;
    border-radius: 18px;
    border: 1px solid #e1ebe6;
}

.icon {
    font-size: 48px;
    margin-bottom: 10px;
}

h1 {
    font-size: 38px;
    margin: 10px 0 15px;
}

h1 span {
    color: #15966f;
}

h2 {
    font-size: 23px;
    margin: 28px 0 10px;
}

h3 {
    margin-bottom: 7px;
}

p {
    color: #66736e;
    margin-bottom: 13px;
}

.info {
    margin-top: 18px;
    padding: 19px;
    background: #effaf5;
    border-radius: 12px;
    border: 1px solid #d5ebe2;
}

.example {
    margin-top: 15px;
    padding: 18px;
    background: #fbfdfc;
    border-left: 4px solid #15966f;
    border-radius: 8px;
    border-top: 1px solid #e3ebe7;
    border-right: 1px solid #e3ebe7;
    border-bottom: 1px solid #e3ebe7;
}

.data-list {
    margin-top: 18px;
    display: grid;
    gap: 12px;
}

.data-item {
    padding: 17px;
    background: #effaf5;
    border-radius: 10px;
    border: 1px solid #d5ebe2;
}

.tip {
    margin-top: 12px;
    padding: 17px;
    background: #effaf5;
    border-radius: 10px;
    border: 1px solid #d5ebe2;
}

.question {
    margin-top: 32px;
}

.option {
    display: block;
    width: 100%;
    margin-top: 12px;
    padding: 14px;
    border: 1px solid #ccd8d3;
    background: white;
    border-radius: 9px;
    text-align: left;
    cursor: pointer;
    font-size: 15px;
}

.option:hover {
    background: #effaf5;
    border-color: #15966f;
}

.option input {
    margin-right: 8px;
}

.submit {
    margin-top: 20px;
    width: 100%;
    padding: 13px;
    background: #15966f;
    color: white;
    border: none;
    border-radius: 9px;
    font-weight: 700;
    cursor: pointer;
}

.submit:hover {
    background: #117a5a;
}

.message {
    margin-top: 20px;
    padding: 15px;
    background: #effaf5;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
}

.score {
    margin-top: 20px;
    font-weight: 700;
    color: #15966f;
}

@media (max-width: 600px) {

    .page {
        padding: 25px 14px 45px;
    }

    .card {
        padding: 23px 17px;
    }

    h1 {
        font-size: 30px;
    }

    h2 {
        font-size: 21px;
    }

    .option {
        font-size: 14px;
        padding: 13px;
    }

}

</style>
"""


# ============================================================
# 1. FREE APPS & YOUR DATA
# ============================================================

@app.route("/free-apps", methods=["GET", "POST"])
def free_apps():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "free_apps"
    )

    message = ""

    if request.method == "POST":

        answer = request.form.get("answer", "")

        if answer == "data":

            if complete_activity(
                user_id,
                "free_apps",
                20
            ):

                message = (
                    "Excellent! You understand that some "
                    "free apps can use data as part of their "
                    "business model."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Not quite. Think about how information "
                "about users can support digital services."
            )

    html = learning_css + """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Free Apps & Your Data | DataWise</title>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">📱</div>

<h1>
Free Apps <span>& Your Data</span>
</h1>

<p>
Welcome {{ username }}. Have you ever wondered why
many apps are available without an upfront payment?
The answer is not always simply "because they are free."
</p>

<h2>
Why are some apps free?
</h2>

<p>
A digital service still needs money to operate. Companies
may earn revenue through advertising, subscriptions,
in-app purchases, partnerships, or other business models.
</p>

<p>
In some services, information about users can help the
company understand what people are interested in, improve
features, personalise content, measure advertising or
develop its business strategy.
</p>

<div class="info">

<strong>💡 DataWise Insight</strong>

<p>
"Free" does not always mean that the service has no
business value. A useful question is:
<strong>How does this service make money?</strong>
</p>

</div>

<h2>
What kind of information can matter?
</h2>

<p>
Depending on the service, information such as interests,
preferences, searches, interactions and usage patterns
can help an organisation understand its audience.
</p>

<h2>
🌍 Real-World Examples
</h2>

<div class="example">

<strong>Example 1: Free Video Platform</strong>

<p>
You watch several videos about cooking. The platform may
learn that cooking content interests you and may use that
information to personalise recommendations.
</p>

</div>

<div class="example">

<strong>Example 2: Free Shopping App</strong>

<p>
You search for running shoes several times. Your activity
may help the service understand your interests and show
more relevant products or advertisements.
</p>

</div>

<div class="info">

<strong>🔎 Think Before You Use</strong>

<p>
Before using a free app, consider what information it may
need, what features you are receiving and how the service
could generate revenue.
</p>

</div>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Why can personal data be important to a digital business?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="data"
       required>
It can help businesses understand users,
personalise experiences and support advertising
or other services.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="speed">
It mainly increases the internet speed of every
user's device.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="storage">
It automatically increases the physical storage
capacity of a phone.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="offline">
It allows every online service to operate without
servers or an internet connection.
</label>

<button type="submit"
        class="submit">
Check Answer
</button>

</form>

{% if message %}

<div class="message">
{{ message }}
</div>

{% endif %}

{% if completed %}

<div class="score">
✅ Activity completed! Your Privacy Awareness
Score has been updated.
</div>

{% endif %}

</div>

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        message=message,
        completed=completed
    )


# ============================================================
# 2. WHAT DATA DO APPS COLLECT?
# ============================================================

@app.route("/data-collection", methods=["GET", "POST"])
def data_collection():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "data_collection"
    )

    message = ""

    if request.method == "POST":

        answer = request.form.get("answer", "")

        if answer == "multiple":

            if complete_activity(
                user_id,
                "data_collection",
                20
            ):

                message = (
                    "Correct! Different apps may collect different "
                    "types of information depending on their "
                    "features and permissions."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about why a navigation app and a photo "
                "editing app might need different information."
            )

    html = learning_css + """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>What Data Do Apps Collect? | DataWise</title>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">🔍</div>

<h1>
What Data Do <span>Apps Collect?</span>
</h1>

<p>
Apps do not all collect the same information. The data
an app requests or collects often depends on what the app
does, which features you use and which permissions you give.
</p>

<h2>
Common Types of Data
</h2>

<div class="data-list">

<div class="data-item">

📍 <strong>Location</strong>

<p>
A navigation or delivery app may need location information
to provide directions or location-based services.
</p>

</div>

<div class="data-item">

📷 <strong>Camera & Photos</strong>

<p>
A camera, video or scanning app may request access to your
camera or photos for specific features.
</p>

</div>

<div class="data-item">

👤 <strong>Account Information</strong>

<p>
An app may ask for information such as your name, email
address or username when you create an account.
</p>

</div>

<div class="data-item">

📱 <strong>Device & Usage Information</strong>

<p>
Services may collect information about the device,
app version, interactions or how features are used.
</p>

</div>

<div class="data-item">

❤️ <strong>Interests & Preferences</strong>

<p>
Searches, choices and interactions may help a service
understand what content or products interest you.
</p>

</div>

</div>

<h2>
🌍 Real-World Examples
</h2>

<div class="example">

<strong>Example 1: Navigation App</strong>

<p>
A map application may request location access because it
needs to know your position to provide directions.
</p>

</div>

<div class="example">

<strong>Example 2: Photo Editing App</strong>

<p>
A photo editing application may request access to photos
because selecting and editing your pictures is part of
its main function.
</p>

</div>

<div class="info">

<strong>🔐 DataWise Tip</strong>

<p>
A permission request should make sense for the feature
you want to use. If an app asks for access that seems
unrelated to its main purpose, stop and review the request.
</p>

</div>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Can different apps collect different types of information?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="multiple"
       required>
Yes. The information can depend on the app,
its features and the permissions involved.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="similar">
Usually no. Most apps are required to collect
exactly the same categories of information.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="device">
Only the device manufacturer decides what
information every app can collect.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="automatic">
No. Apps automatically receive all personal
information stored on a device.
</label>

<button class="submit"
        type="submit">
Check Answer
</button>

</form>

{% if message %}

<div class="message">
{{ message }}
</div>

{% endif %}

{% if completed %}

<div class="score">
✅ Activity completed! Your Privacy Awareness
Score has been updated.
</div>

{% endif %}

</div>

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        message=message,
        completed=completed
    )


# ============================================================
# 3. VALUE OF YOUR DATA
# ============================================================

@app.route("/data-value", methods=["GET", "POST"])
def data_value():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "data_value"
    )

    message = ""

    if request.method == "POST":

        answer = request.form.get("answer", "")

        if answer == "insight":

            if complete_activity(
                user_id,
                "data_value",
                20
            ):

                message = (
                    "Correct! Data can provide useful insights "
                    "that help organisations understand users, "
                    "improve services and support relevant "
                    "advertising."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about how information can help a "
                "business understand its users and improve "
                "its services."
            )

    html = learning_css + """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Value of Your Data | DataWise</title>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">💰</div>

<h1>
Value of <span>Your Data</span>
</h1>

<p>
Personal data can be valuable because it can provide
information about people, their interests, choices and
interactions with digital services.
</p>

<h2>
Why can data have value?
</h2>

<p>
When information is analysed, it can help organisations
understand their audiences, improve products, personalise
experiences, measure advertising and make business decisions.
</p>

<p>
The value does not necessarily mean that a company is
literally buying an individual's information for one fixed
price. Data can become useful when it provides information
that supports a particular purpose.
</p>

<div class="info">

<strong>💡 Important Idea</strong>

<p>
There is no single fixed monetary value for every person's
data. Its usefulness can depend on the type of information,
its quality, context, purpose and how it is used.
</p>

</div>

<h2>
What can data tell a business?
</h2>

<div class="data-list">

<div class="data-item">
📊 <strong>Understand Users</strong><br>
Information can help identify common interests,
preferences and patterns.
</div>

<div class="data-item">
🛠️ <strong>Improve Services</strong><br>
Usage information can show which features work well
and which areas may need improvement.
</div>

<div class="data-item">
🎯 <strong>Personalise Experiences</strong><br>
Information can help a service provide content,
recommendations or products that may be relevant.
</div>

<div class="data-item">
📢 <strong>Support Advertising</strong><br>
Information about interests or behaviour may help
businesses make advertising more relevant.
</div>

</div>

<h2>
🌍 Real-World Examples
</h2>

<div class="example">

<strong>Example 1: Music Streaming</strong>

<p>
If you regularly listen to a particular type of music,
a streaming service may use your listening activity to
recommend similar songs or artists.
</p>

</div>

<div class="example">

<strong>Example 2: Online Shopping</strong>

<p>
If many users frequently search for a particular product,
a shopping platform can use these patterns to understand
demand and improve recommendations.
</p>

</div>

<h2>
Remember
</h2>

<p>
Your data may reveal more than one isolated fact. When
different pieces of information are combined, they can
create a clearer picture of interests or behaviour.
</p>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Why can personal data be useful to businesses?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="insight"
       required>
It can provide insights that help organisations
understand users, improve services or support
relevant advertising.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="price">
It always has the same fixed monetary price for
every person and every business.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="automatic">
It automatically makes a business successful
without requiring analysis or decisions.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="hardware">
Its main value is that it physically increases
the processing power of a device.
</label>

<button class="submit"
        type="submit">
Check Answer
</button>

</form>

{% if message %}

<div class="message">
{{ message }}
</div>

{% endif %}

{% if completed %}

<div class="score">
✅ Activity completed! Your Privacy Awareness
Score has been updated.
</div>

{% endif %}

</div>

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        message=message,
        completed=completed
    )


# ============================================================
# 4. PROTECT YOUR PRIVACY
# ============================================================

@app.route("/protect-privacy", methods=["GET", "POST"])
def protect_privacy():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "protect_privacy"
    )

    message = ""

    if request.method == "POST":

        answer = request.form.get("answer", "")

        if answer == "check":

            if complete_activity(
                user_id,
                "protect_privacy",
                15
            ):

                message = (
                    "Excellent! Checking permissions and "
                    "privacy settings is an important privacy habit."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about what you should check before "
                "giving an app access to personal information."
            )

    html = learning_css + """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Protect Your Privacy | DataWise</title>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">🛡️</div>

<h1>
Protect <span>Your Privacy</span>
</h1>

<p>
Privacy protection is not about avoiding every digital
service. It is about making informed choices about what
information you share and who can access it.
</p>

<h2>
Simple Privacy Habits
</h2>

<div class="tip">
🔐 <strong>Review App Permissions</strong><br>
Check which apps can access your location, camera,
microphone, photos or other information.
</div>

<div class="tip">
🔑 <strong>Use Strong and Unique Passwords</strong><br>
Avoid using the same password for important accounts.
</div>

<div class="tip">
👀 <strong>Think Before Sharing</strong><br>
Avoid posting unnecessary personal information publicly.
</div>

<div class="tip">
⚙️ <strong>Check Privacy Settings</strong><br>
Review account and app settings to understand what
information is shared.
</div>

<div class="tip">
🔄 <strong>Keep Apps Updated</strong><br>
Updates can include important security and privacy fixes.
</div>

<h2>
Why Permissions Matter
</h2>

<p>
An app asking for a permission does not automatically mean
that the permission is necessary. Consider whether the
request is connected to a feature you actually use.
</p>

<h2>
🌍 Real-World Examples
</h2>

<div class="example">

<strong>Example 1: Calculator App</strong>

<p>
A simple calculator normally does not need your location
to perform calculations. A location request should therefore
make you stop and consider why it is being requested.
</p>

</div>

<div class="example">

<strong>Example 2: Photo Editing App</strong>

<p>
A photo editor may reasonably need access to selected
photos when you want to edit them. You can still review
whether it needs access to all photos or only selected ones.
</p>

</div>

<div class="info">

<strong>💡 DataWise Privacy Rule</strong>

<p>
Before allowing access, ask:
<strong>What is being requested, why is it needed,
and am I comfortable sharing it?</strong>
</p>

</div>

<div class="question">

<h2>
Quick Check
</h2>

<p>
What is a useful habit before allowing an app to
access personal information?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="check"
       required>
Check whether the permission is necessary for
the app's features and review the privacy settings.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="popular">
Allow the permission whenever an app is popular
or has many downloads.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="default">
Accept the permission because app permissions
are always necessary when requested.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="ignore">
Ignore permission details because privacy settings
cannot affect how an app accesses information.
</label>

<button class="submit"
        type="submit">
Check Answer
</button>

</form>

{% if message %}

<div class="message">
{{ message }}
</div>

{% endif %}

{% if completed %}

<div class="score">
✅ Activity completed! Your Privacy Awareness
Score has been updated.
</div>

{% endif %}

</div>

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        message=message,
        completed=completed
    )


# ============================================================
# 5. COOKIES & TRACKING
# ============================================================

@app.route("/cookies-tracking", methods=["GET", "POST"])
def cookies_tracking():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "cookies_tracking"
    )

    message = ""

    if request.method == "POST":

        answer = request.form.get("answer", "")

        if answer == "remember":

            if complete_activity(
                user_id,
                "cookies_tracking",
                10
            ):

                message = (
                    "Correct! Cookies can help websites remember "
                    "preferences or session information and, "
                    "depending on the type and context, can "
                    "support analytics or tracking."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about information a website may need "
                "to remember during or between visits."
            )

    html = learning_css + """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Cookies & Tracking | DataWise</title>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">🍪</div>

<h1>
Cookies <span>& Tracking</span>
</h1>

<p>
When you visit a website, the website may store small
pieces of information in your browser. These are commonly
called cookies.
</p>

<h2>
What can cookies do?
</h2>

<div class="data-list">

<div class="data-item">
🍪 <strong>Remember Login or Session Information</strong><br>
A website may use cookies to maintain a user's session
while they move between pages.
</div>

<div class="data-item">
🌐 <strong>Remember Preferences</strong><br>
A website may remember choices such as language,
region or certain settings.
</div>

<div class="data-item">
📊 <strong>Support Analytics</strong><br>
Some cookies can help website operators understand
how visitors use pages and features.
</div>

<div class="data-item">
👀 <strong>Support Tracking</strong><br>
Some tracking technologies can be used to understand
browsing behaviour across services or websites,
depending on the technology and setup.
</div>

</div>

<h2>
Cookies and Tracking Are Not Exactly the Same
</h2>

<p>
Cookies are one technology used to store or access
information in a browser. Tracking can involve cookies
and other technologies that help understand user
activity.
</p>

<h2>
🌍 Real-World Examples
</h2>

<div class="example">

<strong>Example 1: Language Preference</strong>

<p>
You visit a website and select Hindi instead of English.
A cookie may help the website remember that preference
when you return.
</p>

</div>

<div class="example">

<strong>Example 2: Online Shopping</strong>

<p>
You add products to an online shopping cart and continue
browsing. Cookies or similar technologies may help the
website remember the items in your session.
</p>

</div>

<div class="info">

<strong>🔐 Why Does This Matter?</strong>

<p>
Understanding cookies and tracking can help you make more
informed decisions when websites ask for consent or provide
privacy choices.
</p>

</div>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Which is one possible purpose of a cookie?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="remember"
       required>
Remember information such as preferences or
session details.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="internet">
Increase the physical speed of the internet
connection for every website.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="hardware">
Increase the physical storage capacity of
the device.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="screen">
Change the physical size and resolution of
the device screen.
</label>

<button class="submit"
        type="submit">
Check Answer
</button>

</form>

{% if message %}

<div class="message">
{{ message }}
</div>

{% endif %}

{% if completed %}

<div class="score">
✅ Activity completed! Your Privacy Awareness
Score has been updated.
</div>

{% endif %}

</div>

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        message=message,
        completed=completed
    )


# ============================================================
# 6. DATAWISE QUIZ - 20 QUESTIONS
# ============================================================

@app.route("/quiz", methods=["GET", "POST"])
def quiz():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    username = session.get("username")

    completed = activity_completed(
        user_id,
        "quiz"
    )

    result = None

    if request.method == "POST":

        answers = {}

        for i in range(1, 21):
            answers[f"q{i}"] = request.form.get(f"q{i}")

        # ====================================================
        # ONE CORRECT ANSWER FOR EACH QUESTION
        # ====================================================

        correct_answers = {

            "q1": "b",
            "q2": "c",
            "q3": "a",
            "q4": "b",
            "q5": "c",

            "q6": "a",
            "q7": "b",
            "q8": "c",
            "q9": "a",
            "q10": "b",

            "q11": "c",
            "q12": "a",
            "q13": "b",
            "q14": "c",
            "q15": "a",

            "q16": "b",
            "q17": "c",
            "q18": "a",
            "q19": "b",
            "q20": "c"

        }

        correct_count = 0

        for question in correct_answers:

            if answers[question] == correct_answers[question]:
                correct_count += 1

        percentage = (correct_count / 20) * 100

        if percentage >= 60:

            if not completed:

                complete_activity(
                    user_id,
                    "quiz",
                    15
                )

                completed = True

            result = (
                "Excellent! You scored "
                + str(correct_count)
                + "/20 ("
                + str(int(percentage))
                + "%). "
                "The quiz activity is completed and "
                "15 Privacy Awareness points have been added."
            )

        else:

            result = (
                "You scored "
                + str(correct_count)
                + "/20 ("
                + str(int(percentage))
                + "%). "
                "You need at least 12/20 (60%) to pass. "
                "Review the DataWise activities and try again."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>DataWise Quiz</title>

<style>

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    background: #f7faf9;
    color: #17221e;
    line-height: 1.6;
}

.page {
    max-width: 900px;
    margin: auto;
    padding: 35px 20px 60px;
}

.back {
    color: #15966f;
    font-weight: 700;
    text-decoration: none;
}

.card {
    margin-top: 25px;
    background: white;
    padding: 35px;
    border-radius: 18px;
    border: 1px solid #e1ebe6;
}

.icon {
    font-size: 48px;
}

h1 {
    font-size: 38px;
    margin: 15px 0;
}

h1 span {
    color: #15966f;
}

.intro {
    color: #66736e;
    margin-bottom: 25px;
}

.quiz-info {
    margin-bottom: 25px;
    padding: 16px 18px;
    background: #effaf5;
    border: 1px solid #d5ebe2;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
}

.question {
    margin-top: 25px;
    padding: 20px;
    background: #fbfdfc;
    border: 1px solid #e3ebe7;
    border-radius: 12px;
}

.question h3 {
    margin-bottom: 12px;
}

.option {
    display: block;
    margin-top: 10px;
    padding: 13px;
    border: 1px solid #ccd8d3;
    border-radius: 8px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
}

.option input {
    margin-right: 8px;
}

.submit {
    width: 100%;
    margin-top: 25px;
    padding: 14px;
    border: none;
    border-radius: 9px;
    background: #15966f;
    color: white;
    font-weight: 700;
    cursor: pointer;
}

.submit:hover {
    background: #117a5a;
}

.result {
    margin-top: 20px;
    padding: 18px;
    background: #effaf5;
    border: 1px solid #d5ebe2;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
}

@media (max-width: 600px) {

    .page {
        padding: 25px 14px 45px;
    }

    .card {
        padding: 22px 16px;
    }

    h1 {
        font-size: 30px;
    }

    .question {
        padding: 16px;
    }

    .option {
        font-size: 14px;
        padding: 11px;
    }

}

</style>

</head>

<body>

<div class="page">

<a href="{{ url_for('dashboard') }}"
   class="back">
← Back to Dashboard
</a>

<div class="card">

<div class="icon">
🧠
</div>

<h1>
Test Your <span>Knowledge</span>
</h1>

<p class="intro">
Hello {{ username }}! Answer all 20 questions
to test your understanding of personal data,
privacy and free digital services.
</p>

<div class="quiz-info">
📊 20 Questions &nbsp; | &nbsp;
✅ Passing Score: 12/20 (60%) &nbsp; | &nbsp;
🏆 Complete the quiz to earn +15 Privacy Awareness points
</div>

<form method="POST"
      id="quizForm">


<!-- ========================================================
     QUESTION 1
========================================================= -->

<div class="question">

<h3>
1. Why can some apps be offered for free?
</h3>

<label class="option">
<input type="radio" name="q1" value="a" required>
The company does not need any resources or
revenue to operate the service.
</label>

<label class="option">
<input type="radio" name="q1" value="b">
They may use advertising, subscriptions,
in-app purchases or other business models.
</label>

<label class="option">
<input type="radio" name="q1" value="c">
The app cannot generate any form of business
value while it is free to download.
</label>

<label class="option">
<input type="radio" name="q1" value="d">
All free apps are funded only by the phone
manufacturer.
</label>

</div>


<!-- QUESTION 2 -->

<div class="question">

<h3>
2. Which information can an app potentially request?
</h3>

<label class="option">
<input type="radio" name="q2" value="a" required>
Only information about the phone's battery level,
regardless of the app's purpose.
</label>

<label class="option">
<input type="radio" name="q2" value="b">
Only the device's screen size and display settings.
</label>

<label class="option">
<input type="radio" name="q2" value="c">
Information such as location, account details
or device-related information.
</label>

<label class="option">
<input type="radio" name="q2" value="d">
Every type of personal information stored on
the device without any permission or restriction.
</label>

</div>


<!-- QUESTION 3 -->

<div class="question">

<h3>
3. Why can data be useful to businesses?
</h3>

<label class="option">
<input type="radio" name="q3" value="a" required>
It can provide insights about users and audiences
that support business decisions and services.
</label>

<label class="option">
<input type="radio" name="q3" value="b">
It automatically increases the processing speed
of every device used by customers.
</label>

<label class="option">
<input type="radio" name="q3" value="c">
It guarantees that a company will always make
a profit regardless of its decisions.
</label>

<label class="option">
<input type="radio" name="q3" value="d">
It has value only because it physically increases
the storage capacity of a computer.
</label>

</div>


<!-- QUESTION 4 -->

<div class="question">

<h3>
4. What is a good privacy habit?
</h3>

<label class="option">
<input type="radio" name="q4" value="a" required>
Accept every permission because apps usually
need complete access to a device.
</label>

<label class="option">
<input type="radio" name="q4" value="b">
Review permissions and privacy settings before
deciding what information to share.
</label>

<label class="option">
<input type="radio" name="q4" value="c">
Use one simple password for all accounts so
it is easier to remember.
</label>

<label class="option">
<input type="radio" name="q4" value="d">
Share account passwords with trusted friends
to avoid losing access to an account.
</label>

</div>


<!-- QUESTION 5 -->

<div class="question">

<h3>
5. What can cookies sometimes help websites do?
</h3>

<label class="option">
<input type="radio" name="q5" value="a" required>
Increase the physical battery capacity of a
mobile device.
</label>

<label class="option">
<input type="radio" name="q5" value="b">
Increase the physical size of a computer screen.
</label>

<label class="option">
<input type="radio" name="q5" value="c">
Remember preferences, session information or
other website-related details.
</label>

<label class="option">
<input type="radio" name="q5" value="d">
Automatically protect every website from all
possible security threats.
</label>

</div>


<!-- QUESTION 6 -->

<div class="question">

<h3>
6. Which is an example of personal data?
</h3>

<label class="option">
<input type="radio" name="q6" value="a" required>
An email address that is connected to a person.
</label>

<label class="option">
<input type="radio" name="q6" value="b">
A mathematical formula that is not connected
to any individual.
</label>

<label class="option">
<input type="radio" name="q6" value="c">
The general colour of a wall in a public building.
</label>

<label class="option">
<input type="radio" name="q6" value="d">
The name of a programming language without
any information about its users.
</label>

</div>


<!-- QUESTION 7 -->

<div class="question">

<h3>
7. Why might a navigation app need location access?
</h3>

<label class="option">
<input type="radio" name="q7" value="a" required>
To increase the physical size of the phone while
the navigation app is running.
</label>

<label class="option">
<input type="radio" name="q7" value="b">
To provide location-based directions or services.
</label>

<label class="option">
<input type="radio" name="q7" value="c">
To increase the battery capacity of the device.
</label>

<label class="option">
<input type="radio" name="q7" value="d">
To automatically download every application
available in the user's area.
</label>

</div>


<!-- QUESTION 8 -->

<div class="question">

<h3>
8. What should you consider before granting an app permission?
</h3>

<label class="option">
<input type="radio" name="q8" value="a" required>
Whether most other users have accepted the
same permission.
</label>

<label class="option">
<input type="radio" name="q8" value="b">
Whether the permission makes the device heavier
or lighter.
</label>

<label class="option">
<input type="radio" name="q8" value="c">
Whether the permission is relevant to the app's
feature and necessary for what you want to do.
</label>

<label class="option">
<input type="radio" name="q8" value="d">
Whether granting every permission will make the
app automatically more secure.
</label>

</div>


<!-- QUESTION 9 -->

<div class="question">

<h3>
9. What is personalized advertising?
</h3>

<label class="option">
<input type="radio" name="q9" value="a" required>
Advertising that may be selected using information
about interests, activity or preferences.
</label>

<label class="option">
<input type="radio" name="q9" value="b">
Advertising that is completely identical for every
user regardless of their interests.
</label>

<label class="option">
<input type="radio" name="q9" value="c">
Advertising that appears only when a device is
completely disconnected from the internet.
</label>

<label class="option">
<input type="radio" name="q9" value="d">
Advertising that cannot be influenced by any
information about how users interact with services.
</label>

</div>


<!-- QUESTION 10 -->

<div class="question">

<h3>
10. Why can usage information be useful to a company?
</h3>

<label class="option">
<input type="radio" name="q10" value="a" required>
It always reveals the user's password whenever
an application is opened.
</label>

<label class="option">
<input type="radio" name="q10" value="b">
It can help identify patterns and improve services
or understand how features are used.
</label>

<label class="option">
<input type="radio" name="q10" value="c">
It automatically prevents all advertisements from
appearing on the service.
</label>

<label class="option">
<input type="radio" name="q10" value="d">
It guarantees that every user will use the service
in exactly the same way.
</label>

</div>


<!-- QUESTION 11 -->

<div class="question">

<h3>
11. Which is a safer password practice?
</h3>

<label class="option">
<input type="radio" name="q11" value="a" required>
Use the same short password for every account
so it is easier to remember.
</label>

<label class="option">
<input type="radio" name="q11" value="b">
Write your password in a public place so you
can access it from anywhere.
</label>

<label class="option">
<input type="radio" name="q11" value="c">
Use strong and unique passwords for important
accounts and avoid sharing them.
</label>

<label class="option">
<input type="radio" name="q11" value="d">
Use your name and date of birth as the password
for all important accounts.
</label>

</div>


<!-- QUESTION 12 -->

<div class="question">

<h3>
12. What does a privacy setting generally control?
</h3>

<label class="option">
<input type="radio" name="q12" value="a" required>
It can control how certain information, permissions
or features are shared or accessed.
</label>

<label class="option">
<input type="radio" name="q12" value="b">
It physically changes the size of the phone screen.
</label>

<label class="option">
<input type="radio" name="q12" value="c">
It guarantees that no website or service can ever
collect any information.
</label>

<label class="option">
<input type="radio" name="q12" value="d">
It automatically deletes every online account
connected to the device.
</label>

</div>


<!-- QUESTION 13 -->

<div class="question">

<h3>
13. Why should app permissions be reviewed regularly?
</h3>

<label class="option">
<input type="radio" name="q13" value="a" required>
Permissions never change, so reviewing them has
no real purpose.
</label>

<label class="option">
<input type="radio" name="q13" value="b">
An app's features, settings or your privacy needs
may change over time.
</label>

<label class="option">
<input type="radio" name="q13" value="c">
Reviewing permissions makes every app work
without an internet connection.
</label>

<label class="option">
<input type="radio" name="q13" value="d">
Reviewing permissions automatically removes all
advertisements from every application.
</label>

</div>


<!-- QUESTION 14 -->

<div class="question">

<h3>
14. What is one possible purpose of analytics?
</h3>

<label class="option">
<input type="radio" name="q14" value="a" required>
To physically repair a computer whenever a
website receives a visitor.
</label>

<label class="option">
<input type="radio" name="q14" value="b">
To automatically increase the storage capacity
of every device using the website.
</label>

<label class="option">
<input type="radio" name="q14" value="c">
To understand patterns in how a website or
service is used.
</label>

<label class="option">
<input type="radio" name="q14" value="d">
To guarantee that every visitor will have the
same online experience.
</label>

</div>


<!-- QUESTION 15 -->

<div class="question">

<h3>
15. What can aggregated data help organisations understand?
</h3>

<label class="option">
<input type="radio" name="q15" value="a" required>
Broader patterns and trends across groups of users.
</label>

<label class="option">
<input type="radio" name="q15" value="b">
The exact thoughts and private opinions of every
individual in the group.
</label>

<label class="option">
<input type="radio" name="q15" value="c">
Only information about the physical hardware
used by each person.
</label>

<label class="option">
<input type="radio" name="q15" value="d">
Nothing useful because information from multiple
users cannot be analysed.
</label>

</div>


<!-- QUESTION 16 -->

<div class="question">

<h3>
16. What is a useful response to an app requesting
unnecessary permission?
</h3>

<label class="option">
<input type="radio" name="q16" value="a" required>
Always accept the request immediately because
the app must know what it is doing.
</label>

<label class="option">
<input type="radio" name="q16" value="b">
Consider whether the permission is actually needed
and deny it if it is not necessary.
</label>

<label class="option">
<input type="radio" name="q16" value="c">
Give the app every available permission to avoid
having to review settings later.
</label>

<label class="option">
<input type="radio" name="q16" value="d">
Delete all privacy settings from the device before
using the application.
</label>

</div>


<!-- QUESTION 17 -->

<div class="question">

<h3>
17. What can tracking technologies sometimes help
organisations understand?
</h3>

<label class="option">
<input type="radio" name="q17" value="a" required>
The exact physical weight of a user's phone.
</label>

<label class="option">
<input type="radio" name="q17" value="b">
The chemical composition of the battery in a device.
</label>

<label class="option">
<input type="radio" name="q17" value="c">
Browsing or interaction patterns, depending on
the technology and context.
</label>

<label class="option">
<input type="radio" name="q17" value="d">
The user's thoughts and feelings without any
interaction or information being available.
</label>

</div>


<!-- QUESTION 18 -->

<div class="question">

<h3>
18. Which action can help reduce unnecessary
data sharing?
</h3>

<label class="option">
<input type="radio" name="q18" value="a" required>
Review permissions and only allow access that
makes sense for the service.
</label>

<label class="option">
<input type="radio" name="q18" value="b">
Give every application access to all available
personal information.
</label>

<label class="option">
<input type="radio" name="q18" value="c">
Post private information publicly so services
can understand you better.
</label>

<label class="option">
<input type="radio" name="q18" value="d">
Use the same account password across all services
so less information is needed.
</label>

</div>


<!-- QUESTION 19 -->

<div class="question">

<h3>
19. Does personal data always have one fixed
monetary value?
</h3>

<label class="option">
<input type="radio" name="q19" value="a" required>
Yes. Every person's data has exactly the same
price in every situation.
</label>

<label class="option">
<input type="radio" name="q19" value="b">
No. Its usefulness and value can depend on context,
type, quality, purpose and how it is used.
</label>

<label class="option">
<input type="radio" name="q19" value="c">
Yes. The value of data never changes based on
the purpose for which it is used.
</label>

<label class="option">
<input type="radio" name="q19" value="d">
No. Personal data can never provide useful
information to an organisation.
</label>

</div>


<!-- QUESTION 20 -->

<div class="question">

<h3>
20. What is the main goal of DataWise?
</h3>

<label class="option">
<input type="radio" name="q20" value="a" required>
To encourage people to share as much personal
information as possible.
</label>

<label class="option">
<input type="radio" name="q20" value="b">
To make every digital service paid instead of free.
</label>

<label class="option">
<input type="radio" name="q20" value="c">
To help people understand their data and make
more informed privacy decisions.
</label>

<label class="option">
<input type="radio" name="q20" value="d">
To prevent people from using apps and websites
that collect any type of information.
</label>

</div>


<button type="submit"
        class="submit">
Submit Quiz
</button>

</form>

{% if result %}

<div class="result">
{{ result }}
</div>

{% endif %}

</div>

</div>

</body>

</html>
"""

    return render_template_string(
        html,
        username=username,
        result=result
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(url_for("index"))


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
        use_reloader=False
    )
