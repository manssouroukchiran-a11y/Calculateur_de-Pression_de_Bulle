from flask import Flask, render_template, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

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

        p_bulle = x1 * psat1 + x2 * psat2
        y1 = (x1 * psat1) / p_bulle
        y2 = (x2 * psat2) / p_bulle

        somme_y = y1 + y2
        verif_y = abs(somme_y - 1) < 1e-6

        return render_template('index.html',
            x1=x1, x2=round(x2, 4),
            psat1=psat1, psat2=psat2,
            p_bulle=round(p_bulle, 4),
            y1=round(y1, 4),
            y2=round(y2, 4),
            somme_y=round(somme_y, 4),
            verif_y=verif_y
        )

    except ValueError:
        erreur = "Veuillez entrer des nombres valides !"
        return render_template('index.html', erreur=erreur)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))