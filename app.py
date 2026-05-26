from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from functools import wraps
import sqlite3, random, string, os, urllib.parse
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'arin_secret_key_2026'
app.permanent_session_lifetime = timedelta(days=365)

@app.before_request
def make_session_permanent():
    session.permanent = True

APP_NAME = 'أرين'
ADMIN_PHONES = ['783234925', '779505979', '773852062']
ADMIN_PASSWORD = '78323'
RESERVATION_PHONE = '773852062'
MAINTENANCE_PHONE = '779505979'
PROGRAMMING_PHONE = '783234925'

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'laqta.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        tables = [
            'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT UNIQUE, password TEXT, points INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0, referral_code TEXT, referred_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, original_price INTEGER, image TEXT, description TEXT, category TEXT DEFAULT "general", stock INTEGER DEFAULT 1, status TEXT DEFAULT "available", is_rare INTEGER DEFAULT 0, currency TEXT DEFAULT "ر.ي", created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, customer_name TEXT, phone TEXT, part_name TEXT, status TEXT DEFAULT "pending", created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS user_devices (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, device_name TEXT, part_name TEXT, purchase_date TEXT, warranty_months INTEGER DEFAULT 6, last_notified TEXT)',
            'CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT, phone TEXT, notified INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS otp_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, code TEXT, expires_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, customer_name TEXT, phone TEXT, address TEXT, status TEXT DEFAULT "pending", created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
        ]
        for t in tables:
            conn.execute(t)
        conn.commit()

def migrate_db():
    with get_db() as conn:
        cols = [c[1] for c in conn.execute('PRAGMA table_info(products)').fetchall()]
        if 'currency' not in cols:
            conn.execute('ALTER TABLE products ADD COLUMN currency TEXT DEFAULT "ر.ي"')
        if 'original_price' not in cols:
            conn.execute('ALTER TABLE products ADD COLUMN original_price INTEGER DEFAULT 0')
        if 'is_rare' not in cols:
            conn.execute('ALTER TABLE products ADD COLUMN is_rare INTEGER DEFAULT 0')
        conn.commit()

init_db()
migrate_db()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('سجل دخولك أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('غير مصرح', 'error')
            return redirect(url_for('products'))
        return f(*args, **kwargs)
    return decorated

def generate_code():
    return ''.join(random.choices(string_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_points(uid):
    with get_db() as conn:
        r = conn.execute('SELECT points FROM users WHERE id=?', (uid,)).fetchone()
        return r['points'] if r else 0

def add_points(uid, pts):
    with get_db() as conn:
        conn.execute('UPDATE users SET points=points+? WHERE id=?', (pts, uid))
        conn.commit()

def notify(uid, title, msg):
    with get_db() as conn:
        conn.execute('INSERT INTO notifications (user_id,title,message) VALUES (?,?,?)', (uid, title, msg))
        conn.commit()

def wa_link(phone, msg):
    return 'https://wa.me/967' + phone + '?text=' + urllib.parse.quote(msg)

# ===================== ROUTES =====================

@app.route('/')
def index():
    return render_template('index.html', app_name=APP_NAME)

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('is_admin') else url_for('products'))
    if request.method == 'POST':
        phone = request.form.get('phone','').strip()
        pwd = request.form.get('password','').strip()
        admin_pwd = request.form.get('admin_password','').strip()
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
            if phone in ADMIN_PHONES:
                if admin_pwd != ADMIN_PASSWORD:
                    flash('باسورد الأدمن غلط', 'error')
                    return render_template('login.html', app_name=APP_NAME, is_admin_phone=True, phone=phone)
                if not user:
                    conn.execute('INSERT INTO users (name,phone,password,is_admin,referral_code) VALUES (?,?,?,1,?)', ('أدمن '+phone, phone, pwd, generate_code()))
                    conn.commit()
                    user = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_phone'] = user['phone']
                session['is_admin'] = True
                session.permanent = True
                flash('أهلاً أدمن!', 'success')
                return redirect(url_for('admin_dashboard'))
            if user and (not user['password'] or user['password']==pwd):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_phone'] = user['phone']
                session['is_admin'] = False
                session.permanent = True
                flash('أهلاً '+user['name']+'!', 'success')
                return redirect(url_for('products'))
            flash('رقم أو باسورد غلط', 'error')
    phone = request.args.get('phone','')
    return render_template('login.html', app_name=APP_NAME, is_admin_phone=phone in ADMIN_PHONES, phone=phone)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        step = request.form.get('step','1')
        if step == '1':
            phone = request.form.get('phone','').strip()
            with get_db() as conn:
                if conn.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone():
                    flash('رقم مسجل مسبقاً', 'warning')
                    return redirect(url_for('login', phone=phone))
                otp = ''.join(random.choices(string.digits, k=4))
                exp = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
                conn.execute('INSERT INTO otp_codes (phone,code,expires_at) VALUES (?,?,?)', (phone, otp, exp))
                conn.commit()
            msg = 'كود التحقق من أرين: ' + otp + '\nلا تشاركه مع أحد.'
            flash('تم إرسال كود التحقق لواتساب', 'info')
            return render_template('verify_otp.html', phone=phone, app_name=APP_NAME, wa_url=wa_link(phone, msg), otp=otp)
        elif step == '2':
            phone = request.form.get('phone','').strip()
            otp = request.form.get('otp','').strip()
            name = request.form.get('name','').strip()
            pwd = request.form.get('password','').strip()
            ref = request.form.get('referral_code','').strip()
            with get_db() as conn:
                valid = conn.execute('SELECT * FROM otp_codes WHERE phone=? AND code=? AND expires_at>?', (phone, otp, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).fetchone()
                if not valid:
                    flash('كود غلط أو منتهي', 'error')
                    return render_template('verify_otp.html', phone=phone, app_name=APP_NAME)
                conn.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
                code = generate_code()
                ref_by = None
                if ref:
                    ru = conn.execute('SELECT id FROM users WHERE referral_code=?', (ref,)).fetchone()
                    if ru:
                        ref_by = ru['id']
                        add_points(ref_by, 50)
                        notify(ref_by, 'إحالة ناجحة!', 'حصلت على 50 نقطة من إحالة '+name)
                conn.execute('INSERT INTO users (name,phone,password,referral_code,referred_by,points) VALUES (?,?,?,?,?,50)', (name, phone, pwd, code, ref_by))
                conn.commit()
            flash('تم التسجيل! سجل دخولك', 'success')
            return redirect(url_for('login', phone=phone))
    return render_template('register.html', app_name=APP_NAME)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

# ===================== PRODUCTS =====================

@app.route('/products')
def products():
    cat = request.args.get('cat','')
    search = request.args.get('search','')
    with get_db() as conn:
        q = 'SELECT * FROM products WHERE status="available"'
        params = []
        if cat:
            q += ' AND category=?'
            params.append(cat)
        if search:
            q += ' AND (name LIKE ? OR description LIKE ?)'
            params.extend(['%'+search+'%', '%'+search+'%'])
        q += ' ORDER BY is_rare DESC, id DESC'
        prods = conn.execute(q, params).fetchall()
        cats = [r['category'] for r in conn.execute('SELECT DISTINCT category FROM products').fetchall()]
    pts = get_points(session.get('user_id',0)) if 'user_id' in session else 0
    return render_template('products.html', products=prods, categories=cats, current_cat=cat, search=search, points=pts, app_name=APP_NAME)

@app.route('/product/<int:pid>')
def product_detail(pid):
    with get_db() as conn:
        p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not p:
        flash('المنتج غير موجود', 'error')
        return redirect(url_for('products'))
    return render_template('product_detail.html', product=p, app_name=APP_NAME)

@app.route('/buy/<int:pid>', methods=['POST'])
@login_required
def buy_product(pid):
    name = request.form.get('name','').strip()
    phone = request.form.get('phone','').strip()
    address = request.form.get('address','').strip()
    with get_db() as conn:
        p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if not p or p['stock'] < 1:
            flash('المنتج غير متوفر', 'error')
            return redirect(url_for('products'))
        conn.execute('INSERT INTO orders (user_id,product_id,customer_name,phone,address) VALUES (?,?,?,?,?)', (session['user_id'], pid, name, phone, address))
        conn.execute('UPDATE products SET stock=stock-1 WHERE id=?', (pid,))
        conn.commit()
    msg = 'طلب شراء من أرين:\nالمنتج: '+p['name']+'\nالسعر: '+str(p['price'])+' '+p['currency']+'\nالعميل: '+name+'\nالرقم: '+phone+'\nالعنوان: '+address
    flash('تم إرسال طلبك! سنتواصل معك', 'success')
    return redirect(wa_link(RESERVATION_PHONE, msg))

# ===================== RESERVATION (حجز قطع) =====================
@app.route('/reserve', methods=['GET','POST'])
def reserve():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        phone = request.form.get('phone','').strip()
        part_name = request.form.get('part_name','').strip()
        device_name = request.form.get('device_name','').strip()
        if not name or not phone or not part_name:
            flash('جميع الحقول المطلوبة', 'error')
            return redirect(url_for('reserve'))
        with get_db() as conn:
            user_id = session.get('user_id')
            conn.execute('INSERT INTO reservations (user_id,customer_name,phone,part_name) VALUES (?,?,?,?)', (user_id, name, phone, part_name))
            conn.commit()
        msg = 'حجز قطعة غيار من أرين:\nالعميل: '+name+'\nالرقم: '+phone+'\nالقطعة: '+part_name+'\nالجهاز: '+device_name
        return redirect(wa_link(RESERVATION_PHONE, msg))
    return render_template('reserve.html', app_name=APP_NAME)

# ===================== MAINTENANCE =====================
@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', app_name=APP_NAME, phone=MAINTENANCE_PHONE)

@app.route('/maintenance/book', methods=['POST'])
def maintenance_book():
    name = request.form.get('name','').strip()
    phone = request.form.get('phone','').strip()
    device = request.form.get('device','').strip()
    issue = request.form.get('issue','').strip()
    msg = 'حجز صيانة من أرين:\nالعميل: '+name+'\nالرقم: '+phone+'\nالجهاز: '+device+'\nالمشكلة: '+issue
    flash('تم إرسال طلب الصيانة!', 'success')
    return redirect(wa_link(MAINTENANCE_PHONE, msg))

# ===================== PROGRAMMING =====================
@app.route('/programming')
def programming():
    return render_template('programming.html', app_name=APP_NAME, phone=PROGRAMMING_PHONE)

@app.route('/programming/book', methods=['POST'])
def programming_book():
    name = request.form.get('name','').strip()
    phone = request.form.get('phone','').strip()
    service = request.form.get('service','').strip()
    details = request.form.get('details','').strip()
    msg = 'طلب برمجة من أرين:\nالعميل: '+name+'\nالرقم: '+phone+'\nالخدمة: '+service+'\nالتفاصيل: '+details
    flash('تم إرسال طلب البرمجة!', 'success')
    return redirect(wa_link(PROGRAMMING_PHONE, msg))

# ===================== DEVICES & WARRANTY =====================
@app.route('/my-devices')
@login_required
def my_devices():
    with get_db() as conn:
        devs = conn.execute('SELECT * FROM user_devices WHERE user_id=?', (session['user_id'],)).fetchall()
    return render_template('my_devices.html', devices=devs, app_name=APP_NAME)

@app.route('/add-device', methods=['POST'])
@login_required
def add_device():
    device_name = request.form.get('device_name','').strip()
    part_name = request.form.get('part_name','').strip()
    purchase_date = request.form.get('purchase_date','').strip()
    warranty = int(request.form.get('warranty_months','6'))
    with get_db() as conn:
        conn.execute('INSERT INTO user_devices (user_id,device_name,part_name,purchase_date,warranty_months) VALUES (?,?,?,?,?)', (session['user_id'], device_name, part_name, purchase_date, warranty))
        conn.commit()
    flash('تم إضافة الجهاز', 'success')
    return redirect(url_for('my_devices'))

# ===================== LOYALTY POINTS =====================
@app.route('/points')
@login_required
def points_page():
    pts = get_points(session['user_id'])
    with get_db() as conn:
        hist = conn.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20', (session['user_id'],)).fetchall()
    return render_template('points.html', points=pts, history=hist, app_name=APP_NAME)

# ===================== NOTIFICATIONS =====================
@app.route('/notifications')
@login_required
def notifications():
    with get_db() as conn:
        nots = conn.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC', (session['user_id'],)).fetchall()
        conn.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (session['user_id'],))
        conn.commit()
    return render_template('notifications.html', notifications=nots, app_name=APP_NAME)

# ===================== ADMIN =====================
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    with get_db() as conn:
        users_count = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
        products_count = conn.execute('SELECT COUNT(*) as c FROM products').fetchone()['c']
        orders_count = conn.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
        reservations_count = conn.execute('SELECT COUNT(*) as c FROM reservations').fetchone()['c']
        recent_orders = conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 10').fetchall()
        recent_reservations = conn.execute('SELECT * FROM reservations ORDER BY id DESC LIMIT 10').fetchall()
    return render_template('admin_dashboard.html', users=users_count, products=products_count, orders=orders_count, reservations=reservations_count, recent_orders=recent_orders, recent_reservations=recent_reservations, app_name=APP_NAME)

@app.route('/admin/products', methods=['GET','POST'])
@login_required
@admin_required
def admin_products():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name','').strip()
            price = int(request.form.get('price','0'))
            original = int(request.form.get('original_price','0'))
            desc = request.form.get('description','').strip()
            cat = request.form.get('category','general').strip()
            stock = int(request.form.get('stock','1'))
            rare = 1 if request.form.get('is_rare') else 0
            currency = request.form.get('currency','ر.ي').strip()
            img = 'default.png'
            if 'image' in request.files:
                f = request.files['image']
                if f and allowed_file(f.filename):
                    fn = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + f.filename
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                    img = 'uploads/' + fn
            with get_db() as conn:
                conn.execute('INSERT INTO products (name,price,original_price,image,description,category,stock,is_rare,currency) VALUES (?,?,?,?,?,?,?,?,?)', (name, price, original, img, desc, cat, stock, rare, currency))
                conn.commit()
            flash('تم إضافة المنتج', 'success')
        elif action == 'delete':
            pid = request.form.get('product_id')
            with get_db() as conn:
                conn.execute('DELETE FROM products WHERE id=?', (pid,))
                conn.commit()
            flash('تم الحذف', 'success')
        elif action == 'edit':
            pid = request.form.get('product_id')
            name = request.form.get('name','').strip()
            price = int(request.form.get('price','0'))
            original = int(request.form.get('original_price','0'))
            desc = request.form.get('description','').strip()
            cat = request.form.get('category','general').strip()
            stock = int(request.form.get('stock','1'))
            rare = 1 if request.form.get('is_rare') else 0
            currency = request.form.get('currency','ر.ي').strip()
            with get_db() as conn:
                conn.execute('UPDATE products SET name=?,price=?,original_price=?,description=?,category=?,stock=?,is_rare=?,currency=? WHERE id=?', (name, price, original, desc, cat, stock, rare, currency, pid))
                conn.commit()
            flash('تم التعديل', 'success')
        return redirect(url_for('admin_products'))
    with get_db() as conn:
        prods = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    return render_template('admin_products.html', products=prods, app_name=APP_NAME)

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    with get_db() as conn:
        orders = conn.execute('SELECT orders.*, products.name as product_name FROM orders LEFT JOIN products ON orders.product_id=products.id ORDER BY orders.id DESC').fetchall()
    return render_template('admin_orders.html', orders=orders, app_name=APP_NAME)

@app.route('/admin/reservations')
@login_required
@admin_required
def admin_reservations():
    with get_db() as conn:
        res = conn.execute('SELECT * FROM reservations ORDER BY id DESC').fetchall()
    return render_template('admin_reservations.html', reservations=res, app_name=APP_NAME)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    with get_db() as conn:
        users = conn.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    return render_template('admin_users.html', users=users, app_name=APP_NAME)

# ===================== API =====================
@app.route('/api/points')
def api_points():
    if 'user_id' not in session:
        return jsonify({'points': 0})
    return jsonify({'points': get_points(session['user_id'])})

@app.route('/api/notifications/unread')
def api_unread():
    if 'user_id' not in session:
        return jsonify({'count': 0})
    with get_db() as conn:
        c = conn.execute('SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()['c']
    return jsonify({'count': c})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
