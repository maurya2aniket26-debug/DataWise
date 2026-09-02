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
# Use a fixed path relative to this app.py file.
# This is safer when running on Render.
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

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # PRIVACY SCORE
    # --------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS privacy_scores (
            user_id INTEGER PRIMARY KEY,
            score INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # --------------------------------------------------------
    # COMPLETED ACTIVITIES
    # --------------------------------------------------------

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
# IMPORTANT
# INITIALIZE DATABASE WHEN APPLICATION STARTS
# ============================================================

init_db()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    # Automatically logout any previous login session
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

        # Validation
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

        # Hash password
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

            # New user starts with 0%
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

            # Make sure old users have a score
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

    # Check if already completed
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

    # Record activity
    conn.execute(
        """
        INSERT INTO completed_activities
        (user_id, activity)
        VALUES (?, ?)
        """,
        (user_id, activity)
    )

    # Increase score
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
# ALL DASHBOARD HTML IS INSIDE app.py
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


/* ============================================================
   NAVBAR
============================================================ */

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


/* ============================================================
   HERO
============================================================ */

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


/* ============================================================
   DASHBOARD SECTION
============================================================ */

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


/* ============================================================
   SCORE
============================================================ */

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


/* ============================================================
   CARDS
============================================================ */

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

    box-shadow:
        0 12px 30px rgba(20, 50, 40, 0.08);

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


/* ============================================================
   TIP
============================================================ */

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


/* ============================================================
   FOOTER
============================================================ */

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


/* ============================================================
   MOBILE
============================================================ */

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


    <!-- PRIVACY SCORE -->

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


    <!-- CARDS -->

    <div class="dashboard-grid">


        <!-- CARD 1 -->

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


        <!-- CARD 2 -->

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


        <!-- CARD 3 -->

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


        <!-- CARD 4 -->

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


        <!-- CARD 5 -->

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


        <!-- CARD 6 -->

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
                    "Excellent! You understand that "
                    "some free apps can use data as part "
                    "of their business model."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Not quite. Think about what an app "
                "might receive when you use it."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Free Apps & Your Data | DataWise</title>

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
    margin-bottom: 15px;
}

h1 {
    font-size: 38px;
    margin-bottom: 15px;
}

h1 span {
    color: #15966f;
}

h2 {
    font-size: 23px;
    margin: 28px 0 10px;
}

p {
    color: #66736e;
    margin-bottom: 12px;
}

.info {
    margin-top: 25px;
    padding: 20px;
    background: #effaf5;
    border-radius: 12px;
    border: 1px solid #d5ebe2;
}

.question {
    margin-top: 30px;
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
📱
</div>

<h1>
Free Apps <span>& Your Data</span>
</h1>

<p>
Welcome {{ username }}. Let's understand what
"free" can really mean in the digital world.
</p>

<h2>
Why are some apps free?
</h2>

<p>
Many digital services do not charge users money
directly. Instead, they may earn revenue through
advertising, subscriptions, in-app purchases,
partnerships or other business models.
</p>

<p>
In some cases, information about users can help
companies provide personalised experiences,
measure advertising or understand user behaviour.
</p>

<div class="info">

<strong>
💡 DataWise Insight
</strong>

<p>
When you use a free digital service, it is useful
to ask: "If I am not paying with money, what is
helping support this service?"
</p>

</div>

<h2>
What can become valuable?
</h2>

<p>
Information such as interests, preferences,
activity patterns and interactions can help
organisations understand audiences and improve
their services.
</p>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Why can personal data be important to a digital
business?
</p>

<form method="POST">

<label class="option">
<input type="radio"
       name="answer"
       value="data"
       required>
 It can help businesses understand users,
 personalise experiences and support
 advertising or other services.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="nothing">
 Personal data has no possible business value.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="battery">
 It is mainly used to make a phone battery
 last longer.
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
                    "Correct! Apps may request or collect "
                    "different categories of information "
                    "depending on their features."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think again. Different apps can collect "
                "different types of information."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>What Data Do Apps Collect? | DataWise</title>

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

h2 {
    margin-top: 28px;
    margin-bottom: 10px;
}

p {
    color: #66736e;
    margin-bottom: 12px;
}

.data-list {
    margin-top: 20px;
    display: grid;
    gap: 12px;
}

.data-item {
    padding: 16px;
    background: #effaf5;
    border-radius: 10px;
    border: 1px solid #d5ebe2;
}

.question {
    margin-top: 30px;
}

.option {
    display: block;
    margin-top: 12px;
    padding: 14px;
    border: 1px solid #ccd8d3;
    border-radius: 9px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
}

.submit {
    width: 100%;
    margin-top: 20px;
    padding: 13px;
    border: none;
    border-radius: 9px;
    background: #15966f;
    color: white;
    font-weight: 700;
    cursor: pointer;
}

.message {
    margin-top: 20px;
    padding: 15px;
    background: #effaf5;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
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
🔍
</div>

<h1>
What Data Do <span>Apps Collect?</span>
</h1>

<p>
Not every app collects the same information.
The information requested often depends on what
the app is designed to do.
</p>

<h2>
Examples of Data
</h2>

<div class="data-list">

<div class="data-item">
📍 <strong>Location</strong><br>
May be needed by navigation or location-based
services.
</div>

<div class="data-item">
📷 <strong>Camera & Photos</strong><br>
May be required by photo, video or scanning
features.
</div>

<div class="data-item">
👤 <strong>Account Information</strong><br>
May include information such as a username or
email address.
</div>

<div class="data-item">
📱 <strong>Device & Usage Information</strong><br>
Can include information about how a service is
used or the device it runs on.
</div>

<div class="data-item">
❤️ <strong>Interests & Preferences</strong><br>
Can help services understand what content or
products may be relevant to users.
</div>

</div>

<div class="question">

<h2>
Quick Check
</h2>

<p>
Can different apps collect different types of
information?
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
       value="same">
 No. Every app collects exactly the same data.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="none">
 No app can collect any information.
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
                    "Correct! Data can help organisations "
                    "understand patterns, audiences and "
                    "user preferences."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about how information can help "
                "a business understand its users."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Value of Your Data | DataWise</title>

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

h2 {
    margin-top: 28px;
    margin-bottom: 10px;
}

p {
    color: #66736e;
    margin-bottom: 12px;
}

.box {
    margin-top: 20px;
    padding: 20px;
    background: #effaf5;
    border-radius: 12px;
    border: 1px solid #d5ebe2;
}

.question {
    margin-top: 30px;
}

.option {
    display: block;
    margin-top: 12px;
    padding: 14px;
    border: 1px solid #ccd8d3;
    border-radius: 9px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
}

.submit {
    width: 100%;
    margin-top: 20px;
    padding: 13px;
    border: none;
    border-radius: 9px;
    background: #15966f;
    color: white;
    font-weight: 700;
    cursor: pointer;
}

.message {
    margin-top: 20px;
    padding: 15px;
    background: #effaf5;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
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
💰
</div>

<h1>
Value of <span>Your Data</span>
</h1>

<p>
Personal data can provide useful information about
how people interact with digital services.
</p>

<h2>
Why can data have value?
</h2>

<p>
When information is analysed at scale, it can help
organisations understand audiences, improve
products, personalise experiences and measure
the effectiveness of services or advertising.
</p>

<div class="box">

<strong>
💡 Important Idea
</strong>

<p>
There is no single fixed "price" for one person's
data. Its usefulness and value can depend on the
type of information, context, quality and how it
is used.
</p>

</div>

<h2>
Examples
</h2>

<p>
A person's interests may help a service understand
what content could be relevant. Usage patterns may
help developers improve a product. Aggregated
information can help organisations identify broader
trends.
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
       value="random">
 It automatically turns every app into a bank.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="nothing">
 It can never provide useful information.
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
                    "privacy settings is an important "
                    "privacy habit."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about what you should check "
                "before giving an app access."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Protect Your Privacy | DataWise</title>

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

h2 {
    margin-top: 28px;
    margin-bottom: 10px;
}

p {
    color: #66736e;
    margin-bottom: 12px;
}

.tip {
    margin-top: 15px;
    padding: 17px;
    background: #effaf5;
    border-radius: 10px;
}

.question {
    margin-top: 30px;
}

.option {
    display: block;
    margin-top: 12px;
    padding: 14px;
    border: 1px solid #ccd8d3;
    border-radius: 9px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
}

.submit {
    width: 100%;
    margin-top: 20px;
    padding: 13px;
    border: none;
    border-radius: 9px;
    background: #15966f;
    color: white;
    font-weight: 700;
    cursor: pointer;
}

.message {
    margin-top: 20px;
    padding: 15px;
    background: #effaf5;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
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
🛡️
</div>

<h1>
Protect <span>Your Privacy</span>
</h1>

<p>
Good privacy habits can reduce unnecessary sharing
of personal information.
</p>

<h2>
Simple Privacy Habits
</h2>

<div class="tip">
🔐 Review app permissions regularly.
</div>

<div class="tip">
🔐 Use strong and unique passwords.
</div>

<div class="tip">
🔐 Be careful about information you share publicly.
</div>

<div class="tip">
🔐 Check privacy settings on important accounts.
</div>

<div class="tip">
🔐 Keep apps and devices updated.
</div>

<h2>
Remember
</h2>

<p>
Not every permission requested by an app is
automatically necessary. Consider whether a
permission makes sense for the feature you are
using.
</p>

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
       value="allow">
 Allow every permission without checking.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="ignore">
 Ignore all privacy settings.
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
                    "Correct! Cookies can be used for "
                    "functions such as remembering preferences "
                    "and, depending on the type and context, "
                    "supporting analytics or tracking."
                )

                completed = True

            else:

                message = (
                    "You have already completed this activity."
                )

        else:

            message = (
                "Think about what websites can remember "
                "about a browsing session."
            )

    html = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Cookies & Tracking | DataWise</title>

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

h2 {
    margin-top: 28px;
    margin-bottom: 10px;
}

p {
    color: #66736e;
    margin-bottom: 12px;
}

.info {
    margin-top: 20px;
    padding: 18px;
    background: #effaf5;
    border-radius: 10px;
}

.question {
    margin-top: 30px;
}

.option {
    display: block;
    margin-top: 12px;
    padding: 14px;
    border: 1px solid #ccd8d3;
    border-radius: 9px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
}

.submit {
    width: 100%;
    margin-top: 20px;
    padding: 13px;
    border: none;
    border-radius: 9px;
    background: #15966f;
    color: white;
    font-weight: 700;
    cursor: pointer;
}

.message {
    margin-top: 20px;
    padding: 15px;
    background: #effaf5;
    border-radius: 10px;
    color: #176b4d;
    font-weight: 600;
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
🍪
</div>

<h1>
Cookies <span>& Tracking</span>
</h1>

<p>
Cookies are small pieces of information that websites
can store in a browser. They can serve different
purposes.
</p>

<h2>
What can cookies do?
</h2>

<div class="info">
🍪 Remember login or session information.
</div>

<div class="info">
🍪 Remember preferences such as language or settings.
</div>

<div class="info">
🍪 Support analytics about website usage.
</div>

<div class="info">
🍪 Some tracking technologies can help build
information about browsing behaviour.
</div>

<h2>
Why does this matter?
</h2>

<p>
Understanding cookies and tracking helps you make
more informed choices about privacy and consent
when using websites.
</p>

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
       value="battery">
 Physically charge the phone battery.
</label>

<label class="option">
<input type="radio"
       name="answer"
       value="screen">
 Increase the size of the screen.
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
    padding: 12px;
    border: 1px solid #ccd8d3;
    border-radius: 8px;
    cursor: pointer;
}

.option:hover {
    background: #effaf5;
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
 They never need money or resources.
</label>

<label class="option">
<input type="radio" name="q1" value="b">
 They may use advertising, subscriptions,
 in-app purchases or other business models.
</label>

<label class="option">
<input type="radio" name="q1" value="c">
 They cannot have a business model.
</label>

</div>


<!-- QUESTION 2 -->

<div class="question">

<h3>
2. Which information can an app potentially request?
</h3>

<label class="option">
<input type="radio" name="q2" value="a" required>
 Only battery percentage.
</label>

<label class="option">
<input type="radio" name="q2" value="b">
 Only screen size.
</label>

<label class="option">
<input type="radio" name="q2" value="c">
 Information such as location, account details
 or device-related information.
</label>

</div>


<!-- QUESTION 3 -->

<div class="question">

<h3>
3. Why can data be useful to businesses?
</h3>

<label class="option">
<input type="radio" name="q3" value="a" required>
 It can provide insights about users and audiences.
</label>

<label class="option">
<input type="radio" name="q3" value="b">
 It automatically repairs devices.
</label>

<label class="option">
<input type="radio" name="q3" value="c">
 It has no possible use.
</label>

</div>


<!-- QUESTION 4 -->

<div class="question">

<h3>
4. What is a good privacy habit?
</h3>

<label class="option">
<input type="radio" name="q4" value="a" required>
 Accept every permission without checking.
</label>

<label class="option">
<input type="radio" name="q4" value="b">
 Review permissions and privacy settings.
</label>

<label class="option">
<input type="radio" name="q4" value="c">
 Share passwords with others.
</label>

</div>


<!-- QUESTION 5 -->

<div class="question">

<h3>
5. What can cookies sometimes help websites do?
</h3>

<label class="option">
<input type="radio" name="q5" value="a" required>
 Charge the phone battery.
</label>

<label class="option">
<input type="radio" name="q5" value="b">
 Increase the physical screen size.
</label>

<label class="option">
<input type="radio" name="q5" value="c">
 Remember preferences or session information.
</label>

</div>


<!-- QUESTION 6 -->

<div class="question">

<h3>
6. Which is an example of personal data?
</h3>

<label class="option">
<input type="radio" name="q6" value="a" required>
 An email address connected to a person.
</label>

<label class="option">
<input type="radio" name="q6" value="b">
 A random mathematical equation.
</label>

<label class="option">
<input type="radio" name="q6" value="c">
 The colour of a wall in an empty room.
</label>

</div>


<!-- QUESTION 7 -->

<div class="question">

<h3>
7. Why might a navigation app need location access?
</h3>

<label class="option">
<input type="radio" name="q7" value="a" required>
 To make the phone physically larger.
</label>

<label class="option">
<input type="radio" name="q7" value="b">
 To provide location-based directions or services.
</label>

<label class="option">
<input type="radio" name="q7" value="c">
 To increase the phone's battery capacity.
</label>

</div>


<!-- QUESTION 8 -->

<div class="question">

<h3>
8. What should you consider before granting an app permission?
</h3>

<label class="option">
<input type="radio" name="q8" value="a" required>
 Whether every other user has accepted it.
</label>

<label class="option">
<input type="radio" name="q8" value="b">
 Whether the permission makes the phone heavier.
</label>

<label class="option">
<input type="radio" name="q8" value="c">
 Whether the permission is relevant to the app's feature.
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
 about interests or activity.
</label>

<label class="option">
<input type="radio" name="q9" value="b">
 Advertising that can never use any information.
</label>

<label class="option">
<input type="radio" name="q9" value="c">
 Advertising that only appears when a phone is off.
</label>

</div>


<!-- QUESTION 10 -->

<div class="question">

<h3>
10. Why can usage information be useful to a company?
</h3>

<label class="option">
<input type="radio" name="q10" value="a" required>
 It always reveals a person's password.
</label>

<label class="option">
<input type="radio" name="q10" value="b">
 It can help identify patterns and improve services.
</label>

<label class="option">
<input type="radio" name="q10" value="c">
 It automatically prevents all advertisements.
</label>

</div>


<!-- QUESTION 11 -->

<div class="question">

<h3>
11. Which is a safer password practice?
</h3>

<label class="option">
<input type="radio" name="q11" value="a" required>
 Use the same simple password everywhere.
</label>

<label class="option">
<input type="radio" name="q11" value="b">
 Share your password with friends.
</label>

<label class="option">
<input type="radio" name="q11" value="c">
 Use strong and unique passwords for important accounts.
</label>

</div>


<!-- QUESTION 12 -->

<div class="question">

<h3>
12. What does a privacy setting generally control?
</h3>

<label class="option">
<input type="radio" name="q12" value="a" required>
 It can control how certain information or
 features are shared or accessed.
</label>

<label class="option">
<input type="radio" name="q12" value="b">
 It physically changes the phone screen.
</label>

<label class="option">
<input type="radio" name="q12" value="c">
 It guarantees that no website can ever collect data.
</label>

</div>


<!-- QUESTION 13 -->

<div class="question">

<h3>
13. Why should app permissions be reviewed regularly?
</h3>

<label class="option">
<input type="radio" name="q13" value="a" required>
 Permissions can never change.
</label>

<label class="option">
<input type="radio" name="q13" value="b">
 An app's features or your privacy needs may change.
</label>

<label class="option">
<input type="radio" name="q13" value="c">
 It makes every app run without an internet connection.
</label>

</div>


<!-- QUESTION 14 -->

<div class="question">

<h3>
14. What is one possible purpose of analytics?
</h3>

<label class="option">
<input type="radio" name="q14" value="a" required>
 To physically repair a computer.
</label>

<label class="option">
<input type="radio" name="q14" value="b">
 To increase the size of a device's storage automatically.
</label>

<label class="option">
<input type="radio" name="q14" value="c">
 To understand patterns in how a website or service is used.
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
 The exact thoughts of every individual.
</label>

<label class="option">
<input type="radio" name="q15" value="c">
 Nothing useful.
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
 Always accept it immediately.
</label>

<label class="option">
<input type="radio" name="q16" value="b">
 Consider whether the permission is actually needed.
</label>

<label class="option">
<input type="radio" name="q16" value="c">
 Give the app every permission available.
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
 The physical weight of a phone.
</label>

<label class="option">
<input type="radio" name="q17" value="b">
 The battery chemistry of a device.
</label>

<label class="option">
<input type="radio" name="q17" value="c">
 Browsing or interaction patterns, depending on
 the technology and context.
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
 Give every app access to everything.
</label>

<label class="option">
<input type="radio" name="q18" value="c">
 Post private information publicly.
</label>

</div>


<!-- QUESTION 19 -->

<div class="question">

<h3>
19. Does personal data always have one fixed monetary value?
</h3>

<label class="option">
<input type="radio" name="q19" value="a" required>
 Yes, every person's data has exactly the same price.
</label>

<label class="option">
<input type="radio" name="q19" value="b">
 No. Its usefulness and value can depend on context,
 type, quality and how it is used.
</label>

<label class="option">
<input type="radio" name="q19" value="c">
 Yes, data has no relationship to context.
</label>

</div>


<!-- QUESTION 20 -->

<div class="question">

<h3>
20. What is the main goal of DataWise?
</h3>

<label class="option">
<input type="radio" name="q20" value="a" required>
 To encourage people to share as much information
 as possible.
</label>

<label class="option">
<input type="radio" name="q20" value="b">
 To make every digital service paid.
</label>

<label class="option">
<input type="radio" name="q20" value="c">
 To help people understand their data and make
 more informed privacy decisions.
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
