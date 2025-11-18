from flask import Flask, request, render_template, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload
from sqlalchemy.exc import IntegrityError 

app = Flask(__name__)
app.secret_key = "super_secret_key_change_me_in_production"

# --- SQLAlchemy Configuration ---
Base = declarative_base()
ENGINE = create_engine('sqlite:///sqlalchemy_users.db') 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

# --- Models (No Change) ---
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False) 

class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True, index=True)
    office = Column(String(10))
    zone = Column(String(10))
    bay = Column(String(10))
    stock_items = relationship("Stock", back_populates="location") 

    def __repr__(self):
        return f"<Location(office='{self.office}', zone='{self.zone}', bay='{self.bay}')>"

class Stock(Base):
    __tablename__ = 'stock'
    id = Column(Integer, primary_key=True, index=True)
    serial = Column(String(10), nullable=False)
    mfg = Column(String(10))
    dimen = Column(String(10))
    type = Column(String(10))
    modifier = Column(String(10))
    location_id = Column(Integer, ForeignKey('locations.id'))
    location = relationship("Location", back_populates="stock_items")

    def __repr__(self):
        return f"<Stock(serial='{self.serial}', location_id='{self.location_id}')>"

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(500), nullable=False)
    timestamp = Column(String(50)) 

    def __repr__(self):
        return f"<Note(id='{self.id}', content='{self.content[:20]}...')>"

# --- Database Initialization (No Change) ---
def init_db():
    print("Initializing Database (Creating tables and adding initial data)...")
    
    Base.metadata.create_all(bind=ENGINE) 
    db = SessionLocal()
    
    # create or get TPA-GAR-A location (default)
    default_location = db.query(Location).filter(Location.office == 'TPA').first()
    if not default_location:
        default_location = Location(office='TPA', zone='GAR', bay = 'A')
        db.add(default_location)
        db.commit()
        print(f"Created location 'TPA-GAR-A' with ID: {default_location.id}")

    # create or get CLW-CON-B location (new location for item 1138)
    new_location = db.query(Location).filter(Location.office == 'CLW').first()
    if not new_location:
        new_location = Location(office='CLW', zone='CON', bay='B')
        db.add(new_location)
        db.commit()
        print(f"Created new location 'CLW-CON-B' with ID: {new_location.id}")

    # store user 'max'
    hashed = generate_password_hash('a')
    existing_user = db.query(User).filter(User.username == 'max').first()
    if not existing_user:
        db.add(User(username='max', password_hash=hashed))
        print("Initial user 'max' added.")
    
    # stock 1137 -> TPA-GAR-A
    if not db.query(Stock).filter(Stock.serial == '1137').first():
        db.add(Stock(serial='1137', mfg='sbp', dimen='25x50', type='win', modifier='1', location_id=default_location.id))
        print("Added stock 1137.")
    
    # stock 1138 -> CLW-CON-B
    if not db.query(Stock).filter(Stock.serial == '1138').first():
        db.add(Stock(serial='1138', mfg='pgt', dimen='10x10', type='win', modifier='1', location_id=new_location.id))
        print("Added stock 1138.")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        print("Database commit failed.")
    
    db.close()
    
init_db()

# --- Routes (UPDATED to use render_template) ---

@app.route('/add_stock', methods=['POST'])
def add_stock():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    try:
        new_item = Stock(
            serial=request.form['serial'],
            mfg=request.form.get('mfg'),
            dimen=request.form.get('dimen'),
            type=request.form.get('type'),
            modifier=request.form.get('modifier'),
            location_id=request.form.get('location_id') 
        )
        
    except Exception as e:
        print(f"Form submission error: {e}")
        return redirect(url_for('index'))

    db = SessionLocal()
    db.add(new_item)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        print(f"Error adding stock: Serial {new_item.serial} may already exist.")
    
    db.close()
    return redirect(url_for('index'))

@app.route('/')
def index():
    if session.get('logged_in'):
        db = SessionLocal()
        
        all_users = db.query(User).all()
        all_stock = db.query(Stock).options(joinedload(Stock.location)).all() 
        all_locations = db.query(Location).all()
        
        db.close()
        
        # USE render_template('index.html')
        return render_template(
            'index.html', 
            users=all_users,
            stock=all_stock,
            locations=all_locations
        )
        
    # USE render_template('login.html')
    return render_template('login.html') 

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    
    if user and check_password_hash(user.password_hash, password):
        session['logged_in'] = True
        session['username'] = user.username
        return redirect(url_for('index'))
    else:
        # USE render_template('login.html')
        return render_template('login.html', error="Invalid credentials")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/show_image')
def show_image():
    # USE render_template('image.html')
    return render_template('image.html')

@app.route('/notes')
def view_notes():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    db = SessionLocal()
    all_notes = db.query(Note).order_by(Note.id.desc()).all() 
    db.close()
    
    # USE render_template('notes.html')
    return render_template(
        'notes.html',
        notes=all_notes
    )

@app.route('/add_note', methods=['POST'])
def add_note():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    content = request.form.get('note_content')
    if not content:
        return redirect(url_for('view_notes'))

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_note = Note(content=content, timestamp=current_time)

    db = SessionLocal()
    db.add(new_note)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving note: {e}")
    
    db.close()
    
    return redirect(url_for('view_notes'))


if __name__ == '__main__':
    app.run(debug=False)