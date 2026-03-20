from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.secret_key = 'supersecretkey'


class StatusTask(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    date_changed = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    task = db.relationship('Task', foreign_keys=[task_id], back_populates='status', lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    sector = db.relationship('Sector', foreign_keys=[sector_id], backref='users', lazy=True)
    
    def __repr__(self):
        return self.username
    
    def __str__(self):
        return self.username

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_of_creation = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_sectors', lazy=True)
    
    def __repr__(self):
        return self.name
    
    def __str__(self):
        return self.name

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())
    due_date = db.Column(db.DateTime, nullable=True)
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=True)
    responsible_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    status = db.relationship('StatusTask', back_populates='task', cascade='all, delete-orphan', lazy=True)
    sector = db.relationship('Sector', backref='tasks', lazy=True)
    responsible = db.relationship('User', foreign_keys=[responsible_id], backref='tasks', lazy=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks', lazy=True)

    def __repr__(self):
        return '<Task %r>' % self.title

@app.route('/delete_sector/<int:sector_id>')
def delete_sector(sector_id):
    sector = Sector.query.get(sector_id)
    if sector:
        try:
            db.session.delete(sector)
            db.session.commit()
            flash('Sector deleted successfully!')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting sector: ' + str(e))
    else:
        flash('Sector not found.')
    return redirect(url_for('config'))

@app.route('/config', methods=['GET', 'POST'])
def config():

    if (request.method == 'POST') and (request.form['submit']=='sector'):
        sector_name = request.form['name']
        new_sector = Sector(name=sector_name, created_by_id=User.query.filter_by(username=session.get('username')).first().id)
        try:
            db.session.add(new_sector)
            db.session.commit()
            flash('Sector created successfully!')
            return redirect(url_for('config'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating sector: ' + str(e))
            return redirect(url_for('config'))
    else:
        sectors = Sector.query.all()
        return render_template('config.html', sectors=sectors)

@app.route('/register', methods=['GET', 'POST'])
def register():
    dropdown_sectors = Sector.query.all()
    if request.method == 'POST':
        print("Is Admin: " + request.form['is_admin'])
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        sector = Sector.query.get(request.form['sector']) if request.form['sector'] else None
        is_admin = True if request.form['is_admin'] == "on" else False

        new_user = User(username=username, password=password, name=name, sector=sector, is_admin=is_admin)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('User registered successfully!')
            return redirect(url_for('register'))
        except Exception as e:
            flash('Error registering user: ' + str(e))
            return redirect(url_for('register'))
    else:
        return render_template('register.html', dropdown_sectors=dropdown_sectors)

@app.route('/create_task', methods=['GET', 'POST'])
def create_task():
    user = User.query.filter_by(username=session.get('username')).first()
    
    if not user:
        flash('Usuário não autenticado.')
        return redirect(url_for('login'))
    
    dropdown_users = User.query.all()
    dropdown_sectors = Sector.query.all()
    
    if request.method == 'POST':
        print('Responsible selected in form:', request.form['responsible'])
        task_title = request.form['title']
        task_description = request.form['description']
        task_due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        task_sector = Sector.query.get(request.form['sector']) if request.form['sector'] else None
        task_responsible = User.query.filter_by(username=request.form['responsible']).first()
        new_task = Task(title=task_title, description=task_description, due_date=task_due_date, sector=task_sector, responsible=task_responsible, created_by=user)
        new_status_task = StatusTask(status='Não Iniciada', task=new_task)
        try:
            db.session.add(new_task)
            db.session.add(new_status_task)
            db.session.commit()
            flash('Task created successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating task: ' + str(e))
            return redirect(url_for('create_task'))
    else:
        return render_template('create_task.html', dropdown_users=dropdown_users, dropdown_sectors=dropdown_sectors)

@app.route('/init/<int:task_id>')
def init_task(task_id):
    task = Task.query.get(task_id)
    new_status_task = StatusTask(status='Em Andamento', task=task)
    try:
        db.session.add(task)
        db.session.add(new_status_task)
        db.session.commit()
        flash('Task created successfully!')
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        flash('Error creating task: ' + str(e))
        return redirect(url_for('home'))
    
@app.route('/pause/<int:task_id>')
def pause_task(task_id):
    task = Task.query.get(task_id)
    new_status_task = StatusTask(status='Pausada', task=task)
    try:
        db.session.add(task)
        db.session.add(new_status_task)
        db.session.commit()
        flash('Task created successfully!')
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        flash('Error creating task: ' + str(e))
        return redirect(url_for('home'))
    
@app.route('/finalize/<int:task_id>')
def finalize_task(task_id):
    task = Task.query.get(task_id)
    new_status_task = StatusTask(status='Concluída', task=task)
    try:
        db.session.add(task)
        db.session.add(new_status_task)
        db.session.commit()
        flash('Task created successfully!')
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        flash('Error creating task: ' + str(e))
        return redirect(url_for('home'))

@app.route('/')
def home():
    user = User.query.filter_by(username=session.get('username')).first()
    if not user:
        flash('Usuário não autenticado.')
        return redirect(url_for('login'))

    tasks = Task.query.order_by(Task.date_created).all()
    print('Tasks retrieved from database:')
    print(tasks)
    return render_template('home.html', tasks=tasks)
    
@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Task.query.get_or_404(id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        flash('Task deleted successfully!')
    except Exception as e:
        flash('Error deleting task: ' + str(e))
    return redirect(url_for('home'))

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    user = User.query.filter_by(username=session.get('username')).first()
    dropdown_users = User.query.all()
    dropdown_sectors = Sector.query.all()
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        task.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        task.sector = Sector.query.get(request.form['sector']) if request.form['sector'] else None
        task.responsible = User.query.filter_by(username=request.form['responsible']).first()
        try:
            db.session.commit()
            flash('Task updated successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            flash('Error updating task: ' + str(e))
    else:
        return render_template('update.html', task=task, dropdown_users=dropdown_users, dropdown_sectors=dropdown_sectors)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    session.pop('name', None)
    flash('You were logged out.')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if not user or user.password != request.form['password']:
            error = 'Invalid Credentials. Please try again.'
        else:
            session['logged_in'] = True
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            session['name'] = user.name
            flash('You were successfully logged in.')
            return redirect(url_for('home'))
        
    return render_template('login.html', error=error)

@app.route('/tasks')
def tasks():
    return render_template('tasks.html')

if __name__ == '__main__':
    app.run(debug=True)


