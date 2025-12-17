class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)

class User(db.Model):
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
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime)

class JobPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer)
    url = db.Column(db.String(255))

class Estimate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    labor = db.Column(db.Float)
    parts = db.Column(db.Float)
    total = db.Column(db.Float)
    approved = db.Column(db.Boolean)
    token = db.Column(db.String(64), unique=True)


