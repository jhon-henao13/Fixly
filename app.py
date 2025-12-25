import os, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

import smtplib
from email.message import EmailMessage

from flask_mail import Mail, Mail, Message
from itsdangerous import URLSafeTimedSerializer





load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # O el servidor que uses
app.config['MAIL_PORT'] = 465  # Puerto para SSL
app.config['MAIL_USE_TLS'] = False  # Usa TLS (opcional, dependiendo del servidor)
app.config['MAIL_USE_SSL'] = True  # Usa SSL
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USER")  # Tu dirección de correo
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")  # Tu contraseña
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USER")  # Tu correo como remitente

mail = Mail(app)
    


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

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

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    item = db.Column(db.String(120), nullable=False)
    problem = db.Column(db.Text)
    status = db.Column(db.String(50), default="RECEIVED")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client")

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

class JobLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    change = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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
    wid = current_user.workshop_id

    jobs = Job.query.filter_by(
        workshop_id=wid
    ).order_by(Job.created_at.desc()).limit(5).all()


    stats = {
        "pending": Job.query.filter_by(workshop_id=wid, status="RECEIVED").count(),
        "in_progress": Job.query.filter_by(workshop_id=wid, status="IN_PROGRESS").count(),
        "done": Job.query.filter_by(workshop_id=wid, status="DONE").count(),
        "total": Job.query.filter_by(workshop_id=wid).count()
    }

    return render_template("dashboard.html", jobs=jobs, stats=stats)


@app.route("/jobs")
@login_required
def jobs_list():
    jobs = Job.query.filter_by(workshop_id=current_user.workshop_id).order_by(Job.created_at.desc()).all()
    return render_template("jobs_list.html", jobs=jobs)


# ================= JOBS =================
@app.route("/jobs/new", methods=["GET", "POST"])
@login_required
def job_new():
    if request.method == "POST":
        client = Client.query.filter_by(
            workshop_id=current_user.workshop_id,
            phone=request.form["client_phone"]
        ).first()

        if not client:
            client = Client(
                workshop_id=current_user.workshop_id,
                name=request.form["client_name"],
                phone=request.form["client_phone"]
            )
            db.session.add(client)
            db.session.flush()  # obtiene ID sin commit

        job = Job(
            workshop_id=current_user.workshop_id,
            client_id=client.id,
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

    # Obtener el estado previo
    previous_status = job.status

    job.status = request.form["status"]

    # Crear un log de cambios
    log = JobLog(job_id=job.id, change=f"Status changed from {previous_status} to {job.status}")
    db.session.add(log)

    # Enviar correos electrónicos a cliente y taller
    send_status_update_email(job)

    db.session.commit()
    return redirect(url_for("job_detail", job_id=job.id))


def send_status_update_email(job):
    client = job.client
    workshop = Workshop.query.get(job.workshop_id)

    # Correo para el taller
    msg_workshop = Message(
        f"Estado de trabajo {job.item}",
        sender=os.getenv("MAIL_USER"),
        recipients=[workshop.email]
    )
    msg_workshop.body = f"El trabajo con ID {job.id} ha cambiado de estado a: {job.status}."
    try:
        mail.send(msg_workshop)  # Enviar correo al taller
    except Exception as e:
        print(f"Error al enviar el correo al taller: {e}")

    # Correo para el cliente
    if client.email:
        msg_client = Message(
            f"Actualización de tu trabajo {job.item}",
            sender=os.getenv("MAIL_USER"),
            recipients=[client.email]
        )
        msg_client.body = f"Hola {client.name},\n\nEl estado de tu trabajo ha cambiado a: {job.status}.\n\nGracias por elegirnos."
        try:
            mail.send(msg_client)  # Enviar correo al cliente
        except Exception as e:
            print(f"Error al enviar el correo al cliente: {e}")



@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def job_edit(job_id):
    job = Job.query.get_or_404(job_id)
    if job.workshop_id != current_user.workshop_id:
        abort(403)
    if request.method == "POST":
        job.status = request.form["status"]
        job.estimated_delivery = request.form["estimated_delivery"]
        job.priority = request.form["priority"]
        db.session.commit()
        return redirect(url_for("job_detail", job_id=job.id))
    return render_template("job_edit.html", job=job)




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


@app.route("/clients")
@login_required
def client_list():
    clients = Client.query.filter_by(workshop_id=current_user.workshop_id).all()
    return render_template("client_list.html", clients=clients)




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




@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()

        if user:
            # Generar token para el restablecimiento de contraseña
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)

            # Crear el mensaje
            msg = Message("Restablecer contraseña", recipients=[email])
            msg.body = f"Para restablecer tu contraseña, haz clic en el siguiente enlace: {reset_url}"

            try:
                # Enviar el correo usando Flask-Mail
                mail.send(msg)
                return render_template("forgot_password.html", message="Te hemos enviado un correo para restablecer tu contraseña.")
            except Exception as e:
                print("Error enviando email:", e)
                return render_template("forgot_password.html", message="Hubo un error al enviar el correo.")
        
        return render_template("forgot_password.html", message="No se encontró un usuario con ese correo.")

    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        # Verificar token
        email = s.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hora de validez
    except:
        return "El enlace de restablecimiento ha expirado o es inválido."

    if request.method == "POST":
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user:
            # Establecer nueva contraseña
            user.password = generate_password_hash(password)
            db.session.commit()
            return redirect("/login")
        
    return render_template("reset_password.html", token=token)


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
