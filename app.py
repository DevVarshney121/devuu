import os
from dotenv import load_dotenv

load_dotenv()
from authlib.integrations.flask_client import OAuth
from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector

from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

oauth = OAuth(app)

# Upload folder
app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)



google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

app.secret_key = os.getenv("SECRET_KEY")

db = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="flask_project"
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/services")
def services():


    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, description, icon, category
        FROM services
        WHERE status = 'active'
        ORDER BY id DESC
    """)

    services = cursor.fetchall()

    cursor.close()

    return render_template(
        "services.html",
        services=services
    )

@app.route("/service/<int:id>")
def service_detail(id):

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, description, icon, category
        FROM services
        WHERE id = %s AND status = 'active'
    """, (id,))

    service = cursor.fetchone()

    cursor.close()

    if not service:
        return "Service not found", 404

    return render_template(
        "service_detail.html",
        service=service
    )

@app.route("/request-service/<int:service_id>", methods=["GET", "POST"])
def request_service(service_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM services WHERE id = %s AND status = 'active'",
        (service_id,)
    )

    service = cursor.fetchone()

    cursor.close()

    if not service:
        return "Service not found", 404

    return render_template(
        "request_service.html",
        service=service
    )



@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        cursor = db.cursor()

        sql = """
        INSERT INTO contacts (name, email, message)
        VALUES (%s, %s, %s)
        """

        cursor.execute(sql, (name, email, message))
        db.commit()

        cursor.close()

        return render_template("success.html")

    return render_template("contact.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)

        sql = """
        SELECT * FROM admins
        WHERE username = %s AND password = %s
        """

        cursor.execute(sql, (username, password))

        admin = cursor.fetchone()

        cursor.close()

        if admin:
            session["admin"] = admin["username"]
            return redirect("/admin")

        return "Invalid username or password"

    return render_template("login.html")

@app.route("/admin")
def admin():

    if "admin" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    # All messages
    cursor.execute("SELECT * FROM contacts ORDER BY id DESC")
    contacts = cursor.fetchall()

    # Total messages
    cursor.execute("SELECT COUNT(*) AS total FROM contacts")
    total_messages = cursor.fetchone()["total"]

    # Today's messages
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM contacts
        WHERE DATE(created_at) = CURDATE()
    """)
    today_messages = cursor.fetchone()["total"]

    # This month's messages
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM contacts
        WHERE MONTH(created_at) = MONTH(CURDATE())
        AND YEAR(created_at) = YEAR(CURDATE())
    """)
    month_messages = cursor.fetchone()["total"]

    cursor.close()

    return render_template(
        "admin.html",
        contacts=contacts,
        total_messages=total_messages,
        today_messages=today_messages,
        month_messages=month_messages
    )


@app.route("/logout")
def logout():

    session.pop("admin", None)

    return redirect("/login")


@app.route("/delete/<int:id>")
def delete(id):

    if "admin" not in session:
        return redirect("/login")

    cursor = db.cursor()

    sql = "DELETE FROM contacts WHERE id = %s"

    cursor.execute(sql, (id,))
    db.commit()

    cursor.close()

    return redirect("/admin")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):

    if "admin" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        sql = """
        UPDATE contacts
        SET name = %s, email = %s, message = %s
        WHERE id = %s
        """

        cursor.execute(sql, (name, email, message, id))
        db.commit()

        cursor.close()

        return redirect("/admin")

    cursor.execute(
        "SELECT * FROM contacts WHERE id = %s",
        (id,)
    )

    contact = cursor.fetchone()

    cursor.close()

    return render_template("edit.html", contact=contact)





@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        cursor = db.cursor()

        sql = """
        INSERT INTO users (name, email, password)
        VALUES (%s, %s, %s)
        """

        try:

            cursor.execute(
                sql,
                (name, email, hashed_password)
            )

            db.commit()

        except mysql.connector.Error:

            cursor.close()

            return "Email already registered"

        cursor.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "user_dashboard.html",
        user_name=session["user_name"]
    )

@app.route("/user-logout")
def user_logout():

    session.pop("user_id", None)
    session.pop("user_name", None)

    return redirect("/login")


@app.route("/google/login")
def google_login():

    redirect_uri = url_for(
        "google_callback",
        _external=True
    )

    return google.authorize_redirect(redirect_uri)

@app.route("/google/callback")
def google_callback():

    token = google.authorize_access_token()

    user_info = token.get("userinfo")

    if not user_info:
        return "Google login failed"

    google_id = user_info.get("sub")
    name = user_info.get("name")
    email = user_info.get("email")
    profile_image = user_info.get("picture")

    # Save Google user information in session
    session["google_id"] = google_id
    session["user_name"] = name
    session["user_email"] = email
    session["profile_image"] = profile_image

    print("Google ID:", google_id)
    print("Name:", name)
    print("Email:", email)

    # Redirect to existing dashboard
    return redirect("/user-dashboard")

@app.route("/user-dashboard")
def user_dashboard():
    return render_template(
        "user_dashboard.html",
        user_name=session.get("user_name"),
        user_email=session.get("user_email"),
        profile_image=session.get("profile_image")
    )


@app.route("/add-problem", methods=["GET", "POST"])
def add_problem():

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]

        image = request.files.get("image")

        filename = None

        if image and image.filename:

            filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        user_name = session.get("user_name", "Anonymous")
        user_id = session.get("user_id")

        cursor = db.cursor()

        sql = """
        INSERT INTO problems
        (user_id, user_name, title, description, image)
        VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(
            sql,
            (
                user_id,
                user_name,
                title,
                description,
                filename
            )
        )

        db.commit()

        cursor.close()

        return redirect("/add-problem")

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM problems
        ORDER BY id DESC
    """)

    problems = cursor.fetchall()

    cursor.close()

    return render_template(
        "add_problem.html",
        problems=problems
    )



@app.route("/delete-problem/<int:id>", methods=["POST"])
def delete_problem(id):

    # Sirf admin delete kar sakta hai
    if "admin" not in session:
        return "Unauthorized", 403

    cursor = db.cursor(dictionary=True)

    # Pehle problem ki image ka naam nikalo
    cursor.execute(
        "SELECT image FROM problems WHERE id = %s",
        (id,)
    )

    problem = cursor.fetchone()

    if not problem:
        cursor.close()
        return "Problem not found", 404

    # Database se problem delete karo
    cursor.execute(
        "DELETE FROM problems WHERE id = %s",
        (id,)
    )

    db.commit()

    cursor.close()

    # Image bhi delete karo
    if problem["image"]:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            problem["image"]
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    return redirect("/add-problem")



    # Sirf admin delete kar sakta hai
    if "admin" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    # Pehle problem ki image ka naam nikalo
    cursor.execute(
        "SELECT image FROM problems WHERE id = %s",
        (id,)
    )

    problem = cursor.fetchone()

    if problem:

        # Database se problem delete
        cursor.execute(
            "DELETE FROM problems WHERE id = %s",
            (id,)
        )

        db.commit()

        # Image bhi delete kar do
        if problem["image"]:

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                problem["image"]
            )

            if os.path.exists(image_path):
                os.remove(image_path)

    cursor.close()

    return redirect("/add-problem")


if __name__ == "__main__":
    app.run(debug=True)