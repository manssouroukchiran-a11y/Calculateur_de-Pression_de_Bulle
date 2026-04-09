from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '7394',
    'database': 'thermodynamique'
}

# ─── Formulaire d'inscription ───────────────────────────
class RegisterForm(FlaskForm):

    username = StringField('Nom d utilisateur', validators=[
        DataRequired(message="Le nom est obligatoire."),
        Length(min=3, max=80, message="Entre 3 et 80 caractères.")
    ])

    email = StringField('Email', validators=[
        DataRequired(message="L email est obligatoire."),
        Email(message="Email invalide.")
    ])

    password = PasswordField('Mot de passe', validators=[
        DataRequired(message="Le mot de passe est obligatoire."),
        Length(min=6, message="Minimum 6 caractères.")
    ])

    confirm_password = PasswordField('Confirmer le mot de passe', validators=[
        DataRequired(),
        EqualTo('password', message="Les mots de passe ne correspondent pas.")
    ])

    submit = SubmitField('S inscrire')

    # Vérifie que le username n'existe pas déjà dans MySQL
    def validate_username(self, username):
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            raise ValidationError("Ce nom d utilisateur est déjà pris.")

    # Vérifie que l'email n'existe pas déjà dans MySQL
    def validate_email(self, email):
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            raise ValidationError("Cet email est déjà utilisé.")


# ─── Formulaire de connexion ─────────────────────────────
class LoginForm(FlaskForm):

    username = StringField('Nom d utilisateur', validators=[
        DataRequired(message="Le nom est obligatoire.")
    ])

    password = PasswordField('Mot de passe', validators=[
        DataRequired(message="Le mot de passe est obligatoire.")
    ])

    submit = SubmitField('Se connecter')