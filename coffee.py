# encoding: utf-8

from __future__ import division

from datetime import datetime
import ldap
from wtforms import StringField, PasswordField, BooleanField, IntegerField, SelectField
import json

from flask import Flask, render_template, redirect, request, g, url_for, jsonify, abort
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.wtf import Form

app = Flask(__name__)
login_manager = LoginManager()
app.config.from_object('config')
app.config.from_envvar('COFFEE_SETTINGS', silent=True)

db = SQLAlchemy(app)
login_manager.init_app(app)

def init_db():
    db.create_all()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    name = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    payments = db.relationship('Payment', backref='user', lazy='dynamic')
    consumptions = db.relationship('Consumption', backref='user', lazy='dynamic')

    def __init__(self, name=None, username=None, email=None):
        if name:
            self.name = name
        if username:
            self.username = username
        if email:
            self.email = email

    def __repr__(self):
        return '<User %r>' % self.username

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, amount=None, date=None):
        if amount:
            self.amount = amount
        if not date:
            self.date = datetime.utcnow()
        else:
            self.date = date

    def __repr__(self):
        return '<Payment %r>' % self.id

class Consumption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    units = db.Column(db.Integer)
    amountPaid = db.Column(db.Integer)
    date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, units=None, amountPaid=None, date=None):
        if units:
            self.units = units
        if not amountPaid:
            self.amountPaid = -units * app.config['COFFEE_PRICE']
        else:
            self.amountPaid = amountPaid
        if not date:
            self.date = datetime.utcnow()
        else:
            self.date = date

    def __repr__(self):
        return '<Consumption %r>' % self.id

class BudgetChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime)

    def __init__(self, amount=None, description=None, date=None):
        if amount:
            self.amount = amount
        if description:
            self.description = description
        if not date:
            self.date = datetime.utcnow()
        else:
            self.date = date

    def __repr__(self):
        return '<BudgetChange %r>' % self.description

class LoginForm(Form):
    username = StringField('Username')
    password = PasswordField('Password')
    remember = BooleanField('remember', default=False)

class PaymentForm(Form):
    users = sorted(db.session.query(User).all(), key=lambda x: x.name)
    ids = map(lambda x: x.id, users)
    names = map(lambda x: x.name, users)
    uid = SelectField('Name', choices=zip(ids, names), coerce=int)
    amount = IntegerField('Amount')

class ConsumptionForm(Form):
    users = sorted(db.session.query(User).all(), key=lambda x: x.name)
    ids = map(lambda x: x.id, users)
    names = map(lambda x: x.name, users)
    uid = SelectField('Name', choices=zip(ids, names), coerce=int)
    units = IntegerField('Units')


@app.before_request
def before_request():
    g.user = current_user

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/budget')
def budget():
    changes = db.session.query(BudgetChange).all()
    s = 0
    for c in changes:
        s += c.amount
    return str(s)

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    coffee_price = app.config['COFFEE_PRICE']
    changes = db.session.query(BudgetChange).all()
    s = 0
    for c in changes:
        s += c.amount
    return render_template("global.html", current_budget=render_euros(s), coffee_price=render_euros(coffee_price))

@app.route('/personal')
@login_required
def personal():
    s = 0

    for p in g.user.payments:
        s += p.amount
    for c in g.user.consumptions:
        s += c.amountPaid

    color = ""
    if s > 0:
        color = "green"
    elif s < 0:
        color = "red" 

    print(s)

    return render_template('user.html', current_balance=render_euros(s), balance_color=color)

@app.route('/personal_data.json')
@login_required
def personal_data():
    data = []

    for p in g.user.payments:
        data.append((p.date, p.amount))
    for c in g.user.consumptions:
        data.append((c.date, c.amountPaid))

    result = []
    for (d, a) in sorted(data, key=lambda x: x[0]):
        result.append({'date': str(d.date()), 'amount': a})

    return json.dumps(result)

@app.route('/global_data.json')
@login_required
def global_data():
    changes = db.session.query(BudgetChange).all()
    li = []
    for c in changes:
      li.append((str(c.date.date()), c.amount, c.description))
    result = []
    for l in sorted(li, key=lambda x: x[0]):
        result.append({ 'date': l[0], 'amount': l[1], 'description': l[2] })
    return json.dumps(result)

def ldap_login(username, password, remember=False):
    data = ldap_authenticate(username, password)
    if data:
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            user = User(username=username)
        user.name = data['cn']
        user.email = data['mail']
        login_user(user, remember=remember)
        return True
    else:
        return False

@app.route("/login", methods=['GET', 'POST'])
def login():
    if g.user.is_authenticated():
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        remember = form.remember.data
        user = db.session.query(User).filter_by(username=username).first()
        if not ldap_login(username, password, remember=remember):
            return '<h1>Login failed</h1>'
        return redirect(url_for('index'))
    return render_template('login.html', form=form)


@app.route("/admin")
@login_required
def admin():
    if g.user.username == 'ibabuschkin':
        pform = PaymentForm()
        cform = ConsumptionForm()
        return render_template('admin.html', payment_form=pform, consumption_form=cform)
    else:
        return abort(403)

@app.route("/administrate/<type>", methods=['POST'])
@login_required
def administrate(type):
    if g.user.username == 'ibabuschkin':
        pform = PaymentForm()
        cform = ConsumptionForm()
        if type == 'payment':
            if pform.validate_on_submit():
                uid = pform.uid.data
                amount = pform.amount.data
                user = db.session.query(User).filter_by(id=uid).first()
                user.payments.append(Payment(amount=amount))
                bc = BudgetChange(amount=amount, description='Payment from ' + user.name)
                db.session.add(bc)
                db.session.commit()
                return redirect(url_for('admin'))
        elif type == 'consumption':
            if cform.validate_on_submit():
                uid = cform.uid.data
                units = cform.units.data
                user = db.session.query(User).filter_by(id=uid).first()
                user.consumptions.append(Consumption(units=units))
                db.session.commit()
                return redirect(url_for('admin'))
        return ""
    else:
        return abort(403)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

def render_euros(num):
    minus = ""
    if num < 0:
        num *= -1
        minus = "-"

    euros = num // 100
    cents = num % 100
    return (u'{}{}.{} €'.format(minus, euros, cents))

def ldap_authenticate(username, password):
    ldap_server='e5pc51.physik.tu-dortmund.de'
    base_dn = "cn=users,dc=e5,dc=physik,dc=uni-dortmund,dc=de"
    connect = ldap.open(ldap_server)
    search_filter = "uid=" + username
    try:
        connect.bind_s('uid=' + username +',' + base_dn, password)
        result = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter)
        connect.unbind_s()
        data = result[0][1]
        return data
    except ldap.LDAPError:
        connect.unbind_s()
        return None

login_manager.login_view = 'login'

if __name__ == '__main__':
    app.run(host='')