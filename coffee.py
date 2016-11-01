# coding: utf-8

from __future__ import division, unicode_literals

from datetime import datetime, timedelta, date
import ldap3 as ldap
from wtforms import (StringField,
                     PasswordField,
                     BooleanField,
                     IntegerField,
                     HiddenField,
                     FieldList,
                     FormField,
                     SelectField,
                     TextField)
from wtforms import Form as NoCsrfForm
from wtforms.fields.html5 import DateField

import json

from jinja2 import evalcontextfilter

from flask import (Flask,
                   render_template,
                   redirect,
                   g,
                   url_for,
                   request,
                   send_from_directory,
                   flash,
                   abort)
from flask_login import (LoginManager,
                         login_user,
                         logout_user,
                         current_user,
                         login_required)
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from peewee import fn

import codecs

from subprocess import Popen

from math import exp

from database import User, Transaction, Budget, Service, db

app = Flask(__name__)
login_manager = LoginManager()
app.config.from_object('config')
app.config.from_envvar('COFFEE_SETTINGS', silent=True)
admin = Admin(app, name='E5 MoCA DB ADMIN', template_mode='bootstrap3')

login_manager.init_app(app)

mail = Mail()
mail.init_app(app)

admin.add_view(ModelView(User))
admin.add_view(ModelView(Transaction))
admin.add_view(ModelView(Budget))
admin.add_view(ModelView(Service))


class LoginForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    remember = BooleanField('remember', default=False)


# class PaymentForm(Form):
#     users = User.query.order_by(User.name).all()
#     ids = map(lambda x: x.id, users)
#     names = map(lambda x: '{}{}'.format(x.name, (' ✉️' if x.email else '')),
#                 users)
#     uid = SelectField('Name', choices=zip(ids, names), coerce=int)
#     amount = IntegerField('Amount')
# 
# 
# class ConsumptionForm(Form):
#     users = User.query.order_by(User.name).all()
#     ids = map(lambda x: x.id, users)
#     names = map(lambda x: '{}{}'.format(x.name, (' ✉️' if x.email else '')),
#                 users)
#     uid = SelectField('Name', choices=zip(ids, names), coerce=int)
#     units = FieldList(IntegerField('Units'))
# 
# 
# class ConsumptionSingleForm(NoCsrfForm):
#     user = HiddenField('uid')
#     consumptions = FieldList(IntegerField('consumption', default=0),
#                              min_entries=len(app.config['COFFEE_PRICES']))
# 
# 
# class ConsumptionListForm(Form):
#     users = FieldList(FormField(ConsumptionSingleForm))
# 
# 
# class ExpenseForm(Form):
#     description = TextField('Description')
#     amount = IntegerField('Amount')
#     date = DateField('Date', default=datetime.utcnow)
# 
# 
@app.before_request
def before_request():
    db.connect()
    g.user = current_user


@app.teardown_request
def after_request(callback):
    if not db.is_closed():
        db.close()


@login_manager.user_loader
def load_user(username):
    if app.config['DEBUG']:
        return User(username=username)
    return User.get(User.username == username)


# @app.route('/budget')
# def budget():
#     changes = db.session.query(BudgetChange).all()
#     s = 0
#     for c in changes:
#         s += c.amount
#     return str(s)
# 
# 
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    coffee_prices = app.config['COFFEE_PRICES']
    changes = []  # db.session.query(BudgetChange).all()
    credits = []  # db.session.query(User).all()

    s = 0
    credit = 0
    for c in changes:
        s += c.amount
    for c in credits:
        credit -= c.balance

    return render_template(
        "global.html", current_budget=render_euros(s),
        actual_budget=render_euros(s + credit),
        coffee_prices=coffee_prices
    )


@app.route('/personal/')
@login_required
def personal():
    balance = (Transaction.select(fn.SUM(Transaction.diff))
                          .join(User)
                          .where(User.username==g.user.username)
                          .scalar()) or 0
    if balance > 0:
        balance_type = 'positive'
    else:
        balance_type = 'negative'
    return render_template('personal.html', balance=balance,
                           balance_type=balance_type)


@app.route('/personal_data.json')
@login_required
def personal_data():
    data = []

    for t in Transaction.select().where(Transaction.user==g.user.id):
        data.append((t.date, t.diff))

    result = []
    for (d, a) in sorted(data, key=lambda x: x[0], reverse=True):
        result.append({'date': str(d.date()), 'amount': a})

    return json.dumps(result)


@app.route('/global_data.json')
@login_required
def global_data():
    changes = Transaction.select()
    li = []
    for c in changes:
        li.append((str(c.date.date()), c.diff, c.description))
    result = []
    for l in sorted(li, key=lambda x: x[0]):
        result.append({'date': l[0], 'amount': l[1], 'description': l[2]})
    return json.dumps(result)


def ldap_login(username, password, remember=False):
    if app.config['DEBUG']:
        user, created = User.get_or_create(username=username)
        print(user, user.is_authenticated)
        login_user(user, remember=remember)
        return True
    # data = ldap_authenticate(username, password)
    # if data:
    #     user = db.session.query(User).filter_by(username=username).first()
    #     if not user:
    #         user = User(username=username)
    #         db.session.add(user)
    #     user.name = unicode(data['cn'][0], 'utf-8')
    #     try:
    #         user.email = data['mail'][0]
    #     except KeyError:
    #         print('A user has no mail entry in LDAP!')
    #     db.session.commit()
    #     login_user(user, remember=remember)
    #     return True
    # else:
    #     return False
# 
# 
@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        remember = form.remember.data
        if not ldap_login(username, password, remember=remember):
            return '<h1>Login failed</h1>'
        return redirect(url_for('index'))
    return render_template('login.html', form=form)
# 
# 
# def get_listofshame():
#     users = db.session.query(User).all()
#     entries = []
#     for u in users:
#         entries.append({'name': u.name,
#                         'balance': u.balance,
#                         'active': u.active,
#                         'score': u.score})
#     li = sorted(entries, key=lambda e: (-e['active'], e['balance']))
#     return li
# 
# 
@app.route('/admin/')
@login_required
def admin():
    if is_admin(g.user.username):
        pform = PaymentForm()
        cform = ConsumptionForm()
        for price, title in app.config['COFFEE_PRICES']:
            cform.units.append_entry()
            cform.units[-1].label = title
        eform = ExpenseForm()
        listofshame = get_listofshame()
        return render_template('admin.html', payment_form=pform,
                               consumption_form=cform, expense_form=eform,
                               list_of_shame=listofshame)
    else:
        return abort(403)
# 
# 
# @app.route("/administrate/payment", methods=['POST'])
# @login_required
# def administrate_payment():
#     if is_admin(g.user.username):
#         pform = PaymentForm()
#         if pform.validate_on_submit():
#             uid = pform.uid.data
#             amount = pform.amount.data
#             user = db.session.query(User).filter_by(id=uid).first()
#             payment = Payment(amount=amount)
#             user.payments.append(payment)
#             bc = BudgetChange(amount=amount,
#                               description='Payment from ' + user.name)
#             payment.budgetChanges.append(bc)
#             db.session.add(bc)
#             db.session.commit()
#             if user.email:
#                 msg = Message(u"[Kaffeeministerium] Einzahlung von %s"
#                               % render_euros(amount))
#                 msg.charset = 'utf-8'
#                 msg.add_recipient(user.email)
#                 msg.body = render_template('mail/payment',
#                                            amount=render_euros(amount),
#                                            balance=render_euros(user.balance))
#                 if not app.config['DEBUG']:
#                     mail.send(msg)
#                 else:
#                     print(u'Sending mail \n{}'.format(unicode(msg.as_string(),
#                                                               'utf-8')))
# 
#             return redirect(url_for('admin'))
#     else:
#         return abort(403)
# 
# 
# @app.route("/administrate/consumption", methods=['POST'])
# @login_required
# def administrate_consumption():
#     if is_admin(g.user.username):
#         cform = ConsumptionForm()
#         if cform.validate_on_submit():
#             uid = cform.uid.data
#             user = db.session.query(User).filter_by(id=uid).first()
#             user.active = True
#             for u, c in zip(cform.units.data, app.config['COFFEE_PRICES']):
#                 if(u > 0):
#                     user.consumptions.append(Consumption(units=u,
#                                              amountPaid=-u * c[0]))
#             db.session.commit()
#             if user.balance < app.config['BUDGET_WARN_BELOW'] and user.email:
#                 msg = Message(u"[Kaffeeministerium] Geringes Guthaben!")
#                 msg.charset = 'utf-8'
#                 msg.add_recipient(user.email)
#                 msg.body = render_template('mail/lowbudget',
#                                            balance=render_euros(user.balance))
#                 if not app.config['DEBUG']:
#                     mail.send(msg)
#                 else:
#                     print(u'Sending mail \n{}'.format(unicode(msg.as_string(),
#                                                               'utf-8')))
# 
#             return redirect(url_for('admin'))
#         else:
#             return 'Form not valid'
#     else:
#         return abort(403)
# 
# 
# def warning_mail(user):
#     msg = Message(u"[Kaffeeministerium] Geringes Guthaben!")
#     msg.charset = 'utf-8'
#     msg.add_recipient(user.email)
#     msg.body = render_template('mail/lowbudget',
#                                balance=render_euros(user.balance))
#     if not app.config['DEBUG']:
#         mail.send(msg)
#     else:
#         print(u'Sending mail \n{}'.format(unicode(msg.as_string(), 'utf-8')))
# 
# 
# @app.route('/administrate/consumption/list', methods=['POST', 'GET'])
# @login_required
# def administrate_consumption_list():
#     if is_admin(g.user.username):
#         form = ConsumptionListForm()
#         if request.method == 'POST':
#             if form.validate_on_submit():
#                 for f in form.users.entries:
#                     notify = False
#                     active = False
#                     user = User.query.get(f.user.data)
#                     for units, price in zip(f.consumptions.data,
#                                             app.config['COFFEE_PRICES']):
#                         if units > 0:
#                             user.consumptions.append(Consumption(
#                                 units=units,
#                                 amountPaid=-units * price[0]
#                             ))
#                             print('Consume added for {}'.format(user.name))
#                             notify = True
#                             active = True
#                     db.session.commit()
#                     if (notify and user.email and user.balance
#                             < app.config['BUDGET_WARN_BELOW']):
#                         warning_mail(user)
#                     user.active = active
#             else:
#                 print(form.errors)
#             return redirect(url_for('administrate_consumption_list'))
#         else:
#             users = User.query.order_by(User.active.desc(), User.name).all()
#             for u in users:
#                 form.users.append_entry()
#                 form.users.entries[-1].user.data = u.id
#                 form.users.entries[-1].consumptions.label = u.name
#             return render_template('consumption_list.html', form=form)
#     else:
#         return abort(403)
# 
# 
# @app.route("/administrate/expenses", methods=['POST'])
# @login_required
# def administrate_expenses():
#     if is_admin(g.user.username):
#         eform = ExpenseForm()
#         if eform.validate_on_submit():
#             description = eform.description.data
#             amount = eform.amount.data
#             date = (eform.date.data
#                     if eform.date.data != ''
#                     else datetime.utcnow())
#             bc = BudgetChange(amount=amount,
#                               description=description,
#                               date=date)
#             db.session.add(bc)
#             db.session.commit()
#         else:
#             for field, errors in eform.errors.items():
#                 for error in errors:
#                     flash(u'Error in the %s field - %s'
#                           % (getattr(eform, field).label.text, error))
# 
#         return redirect(url_for('admin'))
#     else:
#         return abort(403)
# 
# 
# @app.route('/administrate/service.pdf')
# @login_required
# def administrate_service_list():
#     services = Service.query.order_by(Service.end_date.desc())[0:5]
#     services = list(reversed(services))
#     string = render_template('service.tex', services=services)
#     with codecs.open('build/service.tex', 'w', 'utf-8') as f:
#         f.write(string)
#     p = Popen(
#         '/Library/Tex/texbin/lualatex --interaction=batchmode'
#         ' --output-directory=build build/service.tex',
#         shell=True
#     )
#     p.wait()
#     return send_from_directory('build', 'service.pdf')
# 
# 
# @app.route('/administrate/service/update/')
# @login_required
# def administrate_service_update():
#     services = []
#     users = User.query.filter(User.active, User.vip == false()).all()
#     users = sorted(users, key=lambda x: x.score)
#     last_service = Service.query.order_by(Service.end_date.desc()).first()
#     last_date = last_service.end_date
#     for u in users[0:5]:
#         s = Service(
#             start=last_date + timedelta(3),
#             end=last_date + timedelta(7),
#         )
#         services.append(s)
#         u.services.append(s)
#         last_date += timedelta(7)
#     db.session.commit()
#     return 'Services Updated: {}'.format(
#         ['{}'.format(st.user.name) for st in services]
#     )
# 
# 
# @app.route('/administrate/list.pdf')
# @login_required
# def administrate_list():
#     users = User.query.filter(User.active).order_by(User.name).all()
#     for u in users:
#         consumptions = sorted(u.consumptions.all(), key=lambda x: x.date)
#         if (consumptions and (
#                 datetime.utcnow() - consumptions[-1].date) > timedelta(90)):
#             u.active = False
#             users.remove(u)
#     db.session.commit()
#     string = render_template('list.tex',
#                              current_date=datetime.utcnow(),
#                              users=users,
#                              vip=app.config['COFFEE_VIPS'])
#     with codecs.open('build/list.tex', 'w', 'utf-8') as f:
#         f.write(string)
#     p = Popen(
#         '/Library/Tex/texbin/lualatex --interaction=batchmode'
#         ' --output-directory=build build/list.tex',
#         shell=True
#     )
#     p.wait()
#     return send_from_directory('build', 'list.pdf')
# 
# 
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
    return (u'{}{}.{:02d} €'.format(minus, euros, cents))


@app.template_filter()
@evalcontextfilter
def euros(eval_ctx, value):
    return render_euros(value)


# def ldap_get(username):
#     ldap_server = app.config['LDAP_HOST']
#     base_dn = app.config['LDAP_SEARCH_BASE']
#     connect = ldap.open(ldap_server, port=app.config['LDAP_PORT'])
#     try:
#         connect.bind_s('', '')
#         result = connect.search_s(base_dn, ldap.SCOPE_SUBTREE,
#                                   'uid={}'.format(username))
#         connect.unbind_s()
#         if result:
#             data = result[0][1]
#             return data
#         else:
#             return None
#     except(ldap.LDAPError, e):
#         print('LDAP error: {}'.format(e))
#         connect.unbind_s()
#         return None
# 
# 
def ldap_authenticate(username, password):
    print('Trying to authenticate {}'.format(username))
    ldap_server = app.config['LDAP_HOST']
    base_dn = app.config['LDAP_SEARCH_BASE']
    connect = ldap.open(ldap_server, port=app.config['LDAP_PORT'])
    search_filter = "uid=" + username
    try:
        connect.bind_s('uid=' + username + ',' + base_dn, password)
        result = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter)
        connect.unbind_s()
        data = result[0][1]
        return data
    except(ldap.LDAPError, e):
        print('LDAP error: {}'.format(e))
        connect.unbind_s()
        return None


login_manager.login_view = 'login'

if __name__ == '__main__':
    if db.is_closed():
        db.connect()
        db.create_tables([User, Transaction], safe=True)
    app.run(host='localhost', port=5001)
