from quart import render_template, url_for, flash, redirect, request

from multiprocessing import Process, Pipe
from flask_login import login_user, current_user, logout_user, login_required

from webcontroller import app, db
from webcontroller.forms import LoginForm, PresenceForm
from webcontroller.models import User

from bot import start_bot


#* Don't really have a use for that yet. Maybe the chat will be the default home later
# @app.route('/home')
# async def home():
#     return await render_template('home.html', posts=posts)


@app.route('/about')
async def about():
    return await render_template('about.html', title="About")


@app.route('/presence', methods=['GET', 'POST'])
@login_required
async def presence():
    form = PresenceForm()
    if form.validate_on_submit():
        app.con.send(["change_pr", form.new_pr.data])
        answer = await get_answer()
        if answer == "done":
            await flash(f"Changed presence to {form.new_pr.data}", "success")
        else:
            await flash("Oops, something went wrong", 'danger')
    return await render_template('presence.html', title="Presence", form=form)


@app.route('/login', methods=['GET', 'POST'])
async def login():
    if current_user.is_authenticated:
        return redirect(url_for('presence'))
    form = LoginForm()
    if form.validate_on_submit():
        if await connect(form.token.data):
            user = User()
            db.session.add(user)
            db.session.commit()
            
            login_user(user)

            name = app.con.recv()
            await flash(f"Logged in as {name}", "success")

            next_page = request.args.get('next') 
            return redirect(next_page) if next_page else redirect(url_for('presence'))
        else:
            await flash("Invalid token, please try again", 'danger')
    return await render_template('login.html', title="Login", form=form)

@app.route('/logout')
async def logout():
    
    app.con.send("close")
    logout_user()
    return redirect(url_for("login"))


async def connect(token):
    app.con, child_con = Pipe()
    #! This saves the connection for everyone regardles of if they are logged in.
    #! (Didn't test between different machines but seemed to keep it between sessions)
    #! I need to find a different way. Maybe use an app factory?
    p = Process(target=start_bot, args=(token, child_con))
    p.start()

    response = await get_answer()
    if response == "ready":
        return True
    elif response == "LoginFailed":
        return False


async def get_answer():
    while True:
        if app.con.poll():
            return app.con.recv()


# def is_logged_in():
#     db = get_db()
