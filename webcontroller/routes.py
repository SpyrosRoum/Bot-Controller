from quart import flask_patch

from quart import render_template, url_for, flash, redirect, request, g

import random
from multiprocessing import Process, Pipe
from flask_login import login_user, current_user, logout_user, login_required

from webcontroller import app, db
from webcontroller.forms import LoginForm, PresenceForm
from webcontroller.models import User

from bot import start_bot


connections = dict()


@app.route('/chat')
@app.route('/')
@login_required
async def chat():
    con = get_con(current_user.get_id())
    con.send("give_guilds")
    guilds = await get_answer() # guilds is a list with dicts that contain the name and id of the guild [{"id": 123, "name": "name1"}, ]
    
    guild = request.args.get("guild", 0, type=int)
    chn = request.args.get("channel", 0, type=int)
    
    if guild == 0:
        return await render_template('chat.html', guilds=guilds)
    else:
        con.send(["give_channels", guild])
        channels = await get_answer()
        chn = random.choice([chn['id'] for chn in channels]) if chn == 0 else chn
        con.send(["give_chat", chn])
        chat = await get_answer()
        

        return await render_template('chat.html', guilds=guilds, channels=channels, chat=chat)



@app.route('/about')
async def about():
    return await render_template('about.html', title="About")


@app.route('/presence', methods=['GET', 'POST'])
@login_required
async def presence():
    form = PresenceForm()
    if form.validate_on_submit():
        con = get_con(current_user.get_id())
        con.send(["change_pr", form.new_pr.data])
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
            connections[str(user.get_id())] = g.con
            
            login_user(user)

            con = get_con(user.get_id())
            name = con.recv()
            await flash(f"Logged in as {name}", "success")

            next_page = request.args.get('next') 
            return redirect(next_page) if next_page else redirect(url_for('presence'))
        else:
            await flash("Invalid token, please try again", 'danger')
    return await render_template('login.html', title="Login", form=form)

@app.route('/logout')
@login_required
async def logout():
    con = get_con(current_user.get_id())
    con.send("close")
    logout_user()
    return redirect(url_for("login"))


async def connect(token):
    g.con, child_con = Pipe()

    p = Process(target=start_bot, args=(token, child_con))
    p.start()

    response = g.con.recv()
    if response == "ready":
        return True
    elif response == "LoginFailed":
        return False


async def get_answer():
    con = get_con(current_user.get_id())
    while True:
        if con.poll():
            return con.recv()


def get_con(user_id):
    return connections[str(user_id)]
