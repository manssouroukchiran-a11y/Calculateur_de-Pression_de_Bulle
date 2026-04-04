from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# 🔗 الاتصال بـ MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:7394@localhost/thermo_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 📦 Table
class Calcul(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    x1 = db.Column(db.Float)
    x2 = db.Column(db.Float)
    psat1 = db.Column(db.Float)
    psat2 = db.Column(db.Float)
    p_bulle = db.Column(db.Float)
    y1 = db.Column(db.Float)
    y2 = db.Column(db.Float)
    
@app.route('/historique')
def historique():
    data = Calcul.query.order_by(Calcul.id.desc()).all()
    return render_template('historique.html', data=data)

@app.route('/')
def home():
    data = Calcul.query.all()
    return render_template('index.html', data=data)

@app.route('/calculer', methods=['POST'])
def calculer():
    erreur = None
    try:
        x1    = float(request.form['x1'])
        psat1 = float(request.form['psat1'])
        psat2 = float(request.form['psat2'])

        if x1 < 0 or x1 > 1:
            erreur = "X1 doit être entre 0 et 1 !"
            return render_template('index.html', erreur=erreur)

        x2 = round(1 - x1, 10)

        if abs(x1 + x2 - 1) > 1e-6:
            erreur = "X1 + X2 incorrect !"
            return render_template('index.html', erreur=erreur)

        # 🧮 Calcul
        p_bulle = x1 * psat1 + x2 * psat2
        y1 = (x1 * psat1) / p_bulle
        y2 = (x2 * psat2) / p_bulle

        somme_y = y1 + y2
        verif_y = abs(somme_y - 1) < 1e-6

        # 💾 تخزين في MySQL
        new_calc = Calcul(
            x1=x1, x2=x2,
            psat1=psat1, psat2=psat2,
            p_bulle=p_bulle,
            y1=y1, y2=y2
        )
        db.session.add(new_calc)
        db.session.commit()

        # ✅ جلب جميع العمليات
        data = Calcul.query.all()

        return render_template('index.html',
            x1=x1, x2=round(x2, 4),
            psat1=psat1, psat2=psat2,
            p_bulle=round(p_bulle, 4),
            y1=round(y1, 4),
            y2=round(y2, 4),
            somme_y=round(somme_y, 4),
            verif_y=verif_y,
            data=data
        )

    except ValueError:
        erreur = "Veuillez entrer des nombres valides !"
        return render_template('index.html', erreur=erreur)

# ⚡ إنشاء الجدول تلقائياً
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)