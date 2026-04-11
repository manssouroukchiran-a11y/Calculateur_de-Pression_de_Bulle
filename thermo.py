from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from collections import defaultdict
import requests
import uuid
import secrets
import re
import time
import os
app = Flask(__name__)
app.secret_key = 'thermo_secret_2024'

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:7394@localhost/thermo_app')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ═══════════════════════════════════════════
# 📧 MAIL
# ═══════════════════════════════════════════
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'manssouroukchiran@gmail.com'
app.config['MAIL_PASSWORD'] = 'jvkmrvmdblxbmigs'

db   = SQLAlchemy(app)
mail = Mail(app)

# ═══════════════════════════════════════════
# 🛡️ DDOS PROTECTION — Rate Limiter
# ═══════════════════════════════════════════

# IP ليلي blocked بشكل دائم (يمكن تزيد يدويًا)
BLOCKED_IPS = set()

# تتبع عدد الطلبات لكل IP
_request_log = defaultdict(list)

# إعدادات الحماية
RATE_LIMIT_REQUESTS = 60    # عدد الطلبات المسموح بها
RATE_LIMIT_WINDOW   = 60    # خلال كم ثانية
RATE_LIMIT_BAN_AT   = 120   # إذا تجاوز هذا العدد → IP تتبلوك أوتوماتيك

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr

@app.before_request
def ddos_protection():
    ip  = get_client_ip()
    now = time.time()

    # إذا IP مبلوكة مباشرة ترجع 403
    if ip in BLOCKED_IPS:
        abort(403)

    # نحيد الطلبات القديمة خارج الـ window
    _request_log[ip] = [t for t in _request_log[ip] if now - t < RATE_LIMIT_WINDOW]
    _request_log[ip].append(now)

    count = len(_request_log[ip])

    # بلوك أوتوماتيك إذا تجاوز الحد الأقصى
    if count > RATE_LIMIT_BAN_AT:
        BLOCKED_IPS.add(ip)
        abort(403)

    # Rate limit عادي
    if count > RATE_LIMIT_REQUESTS:
        abort(429)

@app.errorhandler(429)
def too_many_requests(e):
    return render_template('429.html'), 429

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# ═══════════════════════════════════════════
# 📦 MODÈLES
# ═══════════════════════════════════════════

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),  unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    fname    = db.Column(db.String(100), nullable=False)
    token    = db.Column(db.String(100), nullable=True)
    verified = db.Column(db.Boolean,     default=False)
    is_admin = db.Column(db.Boolean,     default=False)

class Connexion(db.Model):
    id         = db.Column(db.Integer,   primary_key=True)
    user_id    = db.Column(db.Integer)
    username   = db.Column(db.String(80))
    email      = db.Column(db.String(120))
    ip         = db.Column(db.String(60))
    mac        = db.Column(db.String(60))
    ville      = db.Column(db.String(100))
    pays       = db.Column(db.String(100))
    latitude   = db.Column(db.Float)
    longitude  = db.Column(db.Float)
    date_heure = db.Column(db.DateTime, default=datetime.now)

class Calcul(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    x1      = db.Column(db.Float)
    x2      = db.Column(db.Float)
    psat1   = db.Column(db.Float)
    psat2   = db.Column(db.Float)
    p_bulle = db.Column(db.Float)
    y1      = db.Column(db.Float)
    y2      = db.Column(db.Float)
    date    = db.Column(db.DateTime, default=datetime.now)

# ═══════════════════════════════════════════
# 🔒 DECORATEURS
# ═══════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════
# ✅ VALIDATION EMAIL
# ═══════════════════════════════════════════

def email_valide(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Format d'email invalide (exemple: nom@gmail.com)."
    return True, None

# ═══════════════════════════════════════════
# 🌍 GÉOLOCALISATION
# ═══════════════════════════════════════════

def get_real_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    ip = request.remote_addr
    if ip in ('127.0.0.1', '::1', 'localhost'):
        try:
            r = requests.get('https://api.ipify.org?format=json', timeout=4)
            ip = r.json().get('ip', ip)
        except Exception:
            pass
    return ip

def get_geo(ip):
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}', timeout=4)
        d = r.json()
        if d.get('status') == 'success':
            return {
                'ville'    : d.get('city', '?'),
                'pays'     : d.get('country', '?'),
                'latitude' : d.get('lat', 0),
                'longitude': d.get('lon', 0),
            }
    except Exception:
        pass
    return {'ville': '?', 'pays': '?', 'latitude': 0, 'longitude': 0}

def get_mac():
    mac_num = uuid.getnode()
    return ':'.join(f'{(mac_num >> i) & 0xff:02x}' for i in range(0, 48, 8))

# ═══════════════════════════════════════════
# 🔐 LOGIN
# ═══════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))

    erreur   = None
    username = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user     = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if not user.verified:
                erreur = "Confirme ton email avant de te connecter."
                return render_template('login.html', erreur=erreur, username=username)

            session['user_id']  = user.id
            session['username'] = user.username
            session['fname']    = user.fname
            session['email']    = user.email or ''
            session['is_admin'] = bool(user.is_admin)

            ip  = get_real_ip()
            mac = get_mac()
            geo = get_geo(ip)

            db.session.add(Connexion(
                user_id   = user.id,
                username  = user.username,
                email     = user.email or '',
                ip        = ip, mac=mac,
                ville     = geo['ville'],
                pays      = geo['pays'],
                latitude  = geo['latitude'],
                longitude = geo['longitude'],
            ))
            db.session.commit()

            session['lat'] = geo['latitude']
            session['lon'] = geo['longitude']
            session['ip']  = ip
            return redirect(url_for('home'))

        erreur = "Nom d'utilisateur ou mot de passe incorrect."
    return render_template('login.html', erreur=erreur, username=username)

# ═══════════════════════════════════════════
# 📝 REGISTER
# ═══════════════════════════════════════════

@app.route('/register', methods=['GET', 'POST'])
def register():
    erreur  = None
    success = None
    if request.method == 'POST':
        fname    = request.form.get('fname',    '').strip()
        username = request.form.get('username', '').strip()
        email    = request.form.get('email',    '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm',  '')

        ok, msg = email_valide(email)

        if not fname or not username or not email or not password:
            erreur = "Tous les champs sont obligatoires."
        elif len(password) < 6:
            erreur = "Mot de passe : minimum 6 caractères."
        elif password != confirm:
            erreur = "Les mots de passe ne correspondent pas."
        elif not ok:
            erreur = msg
        elif User.query.filter_by(username=username).first():
            erreur = "Ce nom d'utilisateur est déjà pris."
        elif User.query.filter_by(email=email).first():
            erreur = "Cet email est déjà utilisé."
        else:
            token    = secrets.token_urlsafe(32)
            new_user = User(
                fname    = fname,
                username = username,
                email    = email,
                password = generate_password_hash(password),
                token    = token,
                verified = False,
                is_admin = False
            )
            db.session.add(new_user)
            db.session.commit()

            try:
                msg = Message(
                    subject    = 'Confirme ton compte — Thermo App',
                    sender     = app.config['MAIL_USERNAME'],
                    recipients = [email]
                )
                msg.body = f"""Bonjour {fname} !

Clique sur ce lien pour confirmer ton compte :
http://127.0.0.1:5000/confirm/{token}

Si tu n'as pas créé de compte, ignore ce message.

— Thermo App
"""
                mail.send(msg)
                success = "✅ Email de confirmation envoyé ! Vérifie ta boîte mail."
            except Exception as e:
                db.session.delete(new_user)
                db.session.commit()
                erreur = f"Erreur envoi email : {e}"

    return render_template('register.html', erreur=erreur, success=success)

# ═══════════════════════════════════════════
# ✉️ CONFIRMATION
# ═══════════════════════════════════════════

@app.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(token=token).first()
    if not user:
        return "Lien invalide ou expiré.", 404
    user.verified = True
    user.token    = None
    db.session.commit()
    return redirect(url_for('login'))

# ═══════════════════════════════════════════
# 🚪 LOGOUT
# ═══════════════════════════════════════════

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ═══════════════════════════════════════════
# 🗺️ MAP — Admin uniquement
# ═══════════════════════════════════════════

@app.route('/map')
@admin_required
def map_view():
    conn = Connexion.query.order_by(Connexion.id.desc()).first()
    return render_template('map.html', conn=conn)

# ═══════════════════════════════════════════
# 📄 ROUTES
# ═══════════════════════════════════════════

@app.route('/')
@login_required
def home():
    data = Calcul.query.filter_by(
        user_id=session['user_id']
    ).order_by(Calcul.id.desc()).all()
    return render_template('index.html', data=data)

@app.route('/historique')
@login_required
def historique():
    data = Calcul.query.filter_by(
        user_id=session['user_id']
    ).order_by(Calcul.id.desc()).all()
    return render_template('historique.html', data=data)

@app.route('/connexions')
@admin_required
def connexions():
    return render_template('connexions.html',
        data=Connexion.query.order_by(Connexion.id.desc()).all())

@app.route('/calculer', methods=['POST'])
@login_required
def calculer():
    try:
        x1    = float(request.form['x1'])
        psat1 = float(request.form['psat1'])
        psat2 = float(request.form['psat2'])

        data = Calcul.query.filter_by(user_id=session['user_id']).order_by(Calcul.id.desc()).all()

        if x1 < 0 or x1 > 1:
            return render_template('index.html',
                erreur="X1 doit être entre 0 et 1 !", data=data)

        x2      = round(1 - x1, 10)
        p_bulle = x1 * psat1 + x2 * psat2
        y1      = (x1 * psat1) / p_bulle
        y2      = (x2 * psat2) / p_bulle
        somme_y = y1 + y2
        verif_y = abs(somme_y - 1) < 1e-6

        db.session.add(Calcul(
            user_id = session['user_id'],
            x1=x1, x2=x2, psat1=psat1, psat2=psat2,
            p_bulle=p_bulle, y1=y1, y2=y2
        ))
        db.session.commit()

        data = Calcul.query.filter_by(user_id=session['user_id']).order_by(Calcul.id.desc()).all()

        return render_template('index.html',
            x1=x1, x2=round(x2,4), psat1=psat1, psat2=psat2,
            p_bulle=round(p_bulle,4), y1=round(y1,4), y2=round(y2,4),
            somme_y=round(somme_y,4), verif_y=verif_y,
            data=data
        )
    except ValueError:
        data = Calcul.query.filter_by(user_id=session['user_id']).order_by(Calcul.id.desc()).all()
        return render_template('index.html',
            erreur="Veuillez entrer des nombres valides !", data=data)

# ═══════════════════════════════════════════
# ⚡ INIT DB
# ═══════════════════════════════════════════

with app.app_context():
    db.create_all()

    from sqlalchemy import text
    migrations = [
        "ALTER TABLE user      ADD COLUMN email    VARCHAR(120)",
        "ALTER TABLE user      ADD COLUMN token    VARCHAR(100)",
        "ALTER TABLE user      ADD COLUMN verified TINYINT(1) DEFAULT 0",
        "ALTER TABLE user      ADD COLUMN is_admin TINYINT(1) DEFAULT 0",
        "ALTER TABLE connexion ADD COLUMN email    VARCHAR(120)",
        "ALTER TABLE calcul    ADD COLUMN date     DATETIME",
        "ALTER TABLE calcul    ADD COLUMN user_id  INT",
    ]
    for sql in migrations:
        try:
            db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()

    admin = User.query.filter_by(username='admin').first()
    if not admin:
        db.session.add(User(
            username='admin', email='admin@thermo.app',
            password=generate_password_hash('admin123'),
            fname='Admin', verified=True, is_admin=True
        ))
        db.session.commit()
        print("✅ Admin créé — user: admin / pass: admin123")
    else:
        if not admin.is_admin:
            admin.is_admin = True
            db.session.commit()
            print("✅ Admin mis à jour — is_admin=True")

if __name__ == '__main__':
    app.run(debug=True)