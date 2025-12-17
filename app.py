import os, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

import smtplib
from email.message import EmailMessage


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ================= MODELS =================

class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshop.id'))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(255))

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer)
    client_name = db.Column(db.String(120))
    client_phone = db.Column(db.String(50))
    item = db.Column(db.String(120))
    problem = db.Column(db.Text)
    status = db.Column(db.String(50), default="RECEIVED")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Estimate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    labor = db.Column(db.Float)
    parts = db.Column(db.Float)
    total = db.Column(db.Float)
    approved = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(64), unique=True)


class ContactLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    service = db.Column(db.String(120))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



# ================= AUTH =================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("landing.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        workshop = Workshop(
            name=request.form["workshop_name"],
            email=request.form["email"]
        )
        db.session.add(workshop)
        db.session.commit()

        user = User(
            workshop_id=workshop.id,
            email=request.form["email"],
            password=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect("/dashboard")

    return render_template("register.html")







@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ================= DASHBOARD =================

@app.route("/dashboard")
@login_required
def dashboard():
    jobs = Job.query.filter_by(workshop_id=current_user.workshop_id).all()
    return render_template("dashboard.html", jobs=jobs)

# ================= JOBS =================

@app.route("/jobs/new", methods=["GET", "POST"])
@login_required
def job_new():
    if request.method == "POST":
        job = Job(
            workshop_id=current_user.workshop_id,
            client_name=request.form["client_name"],
            client_phone=request.form["client_phone"],
            item=request.form["item"],
            problem=request.form["problem"]
        )
        db.session.add(job)
        db.session.commit()
        return redirect("/dashboard")
    return render_template("job_new.html")

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    if job.workshop_id != current_user.workshop_id:
        abort(403)
    estimate = Estimate.query.filter_by(job_id=job.id).first()
    return render_template("job_detail.html", job=job, estimate=estimate)

@app.route("/jobs/<int:job_id>/status", methods=["POST"])
@login_required
def update_status(job_id):
    job = Job.query.get_or_404(job_id)
    if job.workshop_id != current_user.workshop_id:
        abort(403)
    job.status = request.form["status"]
    db.session.commit()
    return redirect(url_for("job_detail", job_id=job.id))

# ================= ESTIMATES =================

@app.route("/jobs/<int:job_id>/estimate", methods=["GET", "POST"])
@login_required
def estimate_new(job_id):
    job = Job.query.get_or_404(job_id)
    if job.workshop_id != current_user.workshop_id:
        abort(403)

    if request.method == "POST":
        total = float(request.form["labor"]) + float(request.form["parts"])
        estimate = Estimate(
            job_id=job.id,
            description=request.form["description"],
            labor=request.form["labor"],
            parts=request.form["parts"],
            total=total,
            token=secrets.token_hex(16)
        )
        db.session.add(estimate)
        db.session.commit()
        return redirect(url_for("job_detail", job_id=job.id))

    return render_template("estimate_new.html", job=job)

@app.route("/e/<token>", methods=["GET", "POST"])
def public_estimate(token):
    estimate = Estimate.query.filter_by(token=token).first_or_404()
    if request.method == "POST":
        estimate.approved = True
        db.session.commit()
    return render_template("public_estimate.html", estimate=estimate)



@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name")
    email = request.form.get("email")
    service = request.form.get("service")
    message = request.form.get("message")

    # 1️⃣ Guardar en DB
    lead = ContactLead(
        name=name,
        email=email,
        service=service,
        message=message
    )
    db.session.add(lead)
    db.session.commit()

    # 2️⃣ Enviar email a ti
    msg = EmailMessage()
    msg["Subject"] = "Nuevo contacto desde Fixly 🚀"
    msg["From"] = os.getenv("MAIL_USER")
    msg["To"] = "estiguar.dev.emails@gmail.com"

    msg.set_content(f"""
Nuevo lead desde Fixly

Nombre: {name}
Email: {email}
Tipo de servicio: {service}

Mensaje:
{message}
""")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(
                os.getenv("MAIL_USER"),
                os.getenv("MAIL_PASSWORD")
            )
            smtp.send_message(msg)
    except Exception as e:
        print("Error enviando email:", e)

    return redirect(url_for("index") + "#contacto")


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
