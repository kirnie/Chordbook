#!/usr/bin/python3

from flask import Flask, render_template, flash, redirect, url_for, session, request
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

app = Flask(__name__)
app.config.from_pyfile('config_file.cfg')

#Init MySQL
mysql = MySQL(app)

#Homepage - shows all songs available in database
@app.route('/')
def index():
    #Create cursor
    cur = mysql.connection.cursor()

    #Get songs
    result = cur.execute("SELECT * FROM songs")

    songs = cur.fetchall()

    if result > 0:
        return render_template('home.html', songs=songs)
    else:
        return render_template('home.html')

    #Close connection
    cur.close()
    return render_template('home.html')


#Single song - shows details of selected song
@app.route('/songs/<string:id>/')
def song(id):
    #Create cursor
    cur = mysql.connection.cursor()

    #Get song
    result = cur.execute("SELECT * FROM songs WHERE id = %s", [id])

    song = cur.fetchone()

    return render_template('song.html', song=song)

    #Close connection
    cur.close()


#Register Form Class
class RegisterForm(Form):
    name = StringField("Meno", [validators.Length(min=1, max=50)])
    username = StringField("Používateľské meno", [validators.Length(min=4, max=25)])
    email = StringField("Email", [validators.Length(min=6, max=30)])
    password = PasswordField("Heslo", [
        validators.DataRequired(),
        validators.EqualTo("confirm", message="Heslá sa nezhodujú")
        ])
    confirm = PasswordField("Potvrď heslo")


# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        #Create cursor
        cur = mysql.connection.cursor()

        #Check if email or username exists
        email_in_db = cur.execute("SELECT * FROM users WHERE email = %s", [email])
        username_in_db = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if email_in_db > 0:
            flash('Táto emailová adresa sa už používa.', 'danger')
            return redirect(url_for('register'))

        elif username_in_db > 0:
            flash('Používateľské meno sa už používa.', 'danger')
            return redirect(url_for('register'))

        else:
            #Execute query
            cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))

            #Commit to DB
            mysql.connection.commit()

            #Close connection
            cur.close()

            #Message after registration
            flash('Registrácia prebehla úspešne, môžete sa prihlásiť.', 'success')

            #Redirection to login page
            return redirect(url_for('login'))

    return render_template('register.html', form=form)

#User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']

        #Create cursor
        cur = mysql.connection.cursor()

        #Get user by Username from db
        user = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if user > 0:
            #Get stored hash
            data = cur.fetchone()
            password = data['password']

            #Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                #Passed
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('dashboard'))

            else:
                error = 'Zadané prihlasovacie údaje sú nesprávne.'
                return render_template('login.html', error=error)

            #Close connection
            cur.close()

        else:
            error = 'Používateľské meno nebolo nájdené.'
            return render_template('login.html', error=error)

    return render_template('login.html')

#Check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Neautorizovaný prístup! Prosím prihláste sa!', 'danger')
            return redirect(url_for('login'))
    return wrap

#Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    #Create cursor
    cur = mysql.connection.cursor()

    #Get songs
    result = cur.execute("SELECT * FROM songs WHERE author = %s ORDER BY title", [session['username']])

    songs = cur.fetchall()

    if result > 0:
        return render_template('dashboard.html', songs=songs)
    else:
        msg = 'Žiadne piesne'
        return render_template('dashboard.html', msg=msg)

    #Close connection
    cur.close()

#Song Form Class
class SongForm(Form):
    title = StringField("Názov", [validators.Length(min=1, max=200)])
    body = TextAreaField("Text", [validators.Length(min=30)])
    chord = StringField("Key", [validators.Length(min=1, max=10)])

# Add Song
@app.route('/add_song', methods=['GET', 'POST'])
@is_logged_in
def add_song():
    form = SongForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data
        chord = form.chord.data
        author = session['username']

        #Create cursor
        cur = mysql.connection.cursor()

        #Execute
        cur.execute("INSERT INTO songs(chord, title, body, author) VALUES(%s, %s, %s, %s)",(chord, title, body, author))

        #Commit to DB
        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Song created', 'success')

        return redirect(url_for('dashboard'))

    return render_template('add_song.html', form=form)

# Edit Song
@app.route('/edit_song/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_song(id):
    #Create cursor
    cur = mysql.connection.cursor()

    #Get song by id
    result = cur.execute("SELECT * FROM songs WHERE id = %s", [id])

    song = cur.fetchone()

    #Get form
    form = SongForm(request.form)

    #Populate songs
    form.title.data = song['title']
    form.body.data = song['body']
    form.chord.data = song['chord']

    #Save edited data to variables
    if request.method == 'POST' and form.validate():
        title = request.form['title']
        body = request.form['body']
        chord = request.form['chord']

        #Create cursor
        cur = mysql.connection.cursor()
        app.logger.info(title)
        #Execute
        cur.execute("UPDATE songs SET title=%s, body=%s, chord=%s WHERE id = %s", (title, body, chord, id))

        #Commit to DB
        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Song updated', 'success')

        return redirect(url_for('dashboard'))

    return render_template('edit_song.html', form=form)

#Delete song
@app.route('/delete_article/<string:id>', methods=['POST'])
@is_logged_in
def delete_song(id):
    #Create cursor
    cur = mysql.connection.cursor()

    #Execute
    cur.execute("DELETE FROM songs WHERE id = %s", [id])

    #Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    return redirect(url_for('dashboard'))

#Run app (now in debug mode)
if __name__ == '__main__':
    app.run(host='0.0.0.0')
