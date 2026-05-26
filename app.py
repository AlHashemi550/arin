import sqlite3
import random
import os
import urllib.parse
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.permanent_session_lifetime = timedelta(days=365)

# ========== الإعدادات ==========
ADMIN_PHONES = ['783234925', '779505979', '773852062']
ADMIN_PASSWORD = '78323'
RESERVATION_PHONE = '773852062'
MAINTENANCE_PHONE = '779505979'
PROGRAMMING_PHONE = '783234925'
APP_NAME = 'أرين'
SHOP_NAME = 'محل الراشد للجوالات'
SHOP_LOCATION = 'المهرة - الغيضة - الهنجر - سوق بن خودم'
MAP_URL = 'https://www.google.com/maps/search/?api=1&query=Al+Ghaydah+Al+Mahrah+Yemen'

DATABASE = 'laqta.db'

# ========== قاعدة البيانات ==========
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        c = db.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT UNIQUE,
                password TEXT,
                points INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                referral_code TEXT,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL,
                original_price REAL,
                image TEXT,
                description TEXT,
                category TEXT,
                stock INTEGER,
                status TEXT,
                is_rare INTEGER DEFAULT 0,
                currency TEXT DEFAULT "ر.ي",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                customer_name TEXT,
                phone TEXT,
                status TEXT DEFAULT "pending",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # إصلاح: التحقق من أعمدة reservations وإضافتها إذا غير موجودة
        c.execute("PRAGMA table_info(reservations)")
        columns = [col[1] for col in c.fetchall()]
        if 'customer_name' not in columns:
            c.execute("ALTER TABLE reservations ADD COLUMN customer_name TEXT")
        if 'phone' not in columns:
            c.execute("ALTER TABLE reservations ADD COLUMN phone TEXT")
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                device_name TEXT,
                part_name TEXT,
                purchase_date TEXT,
                warranty_months INTEGER,
                last_notified TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_name TEXT,
                phone TEXT,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                code TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()

init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ========== معالج الأخطاء ==========
@app.errorhandler(500)
def internal_error(error):
    return f"""
    <!DOCTYPE html>
    <html dir="rtl"><head><meta charset="UTF-8"><title>خطأ</title>
    <style>
        body {{ background:#000; color:#e74c3c; font-family:Cairo,sans-serif; padding:20px; }}
        .box {{ background:#111; border:1px solid #e74c3c; border-radius:15px; padding:20px; margin:20px 0; }}
        pre {{ color:#888; font-size:0.8rem; overflow-x:auto; }}
    </style></head><body>
    <h2>⚠️ خطأ في السيرفر</h2>
    <div class="box">
        <p><strong>النوع:</strong> {type(error).__name__}</p>
        <p><strong>الرسالة:</strong> {str(error)}</p>
        <hr>
        <pre>{traceback.format_exc()}</pre>
    </div>
    <a href="/" style="color:#d4af37;">🏠 العودة للرئيسية</a>
    </body></html>
    """, 500

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('index'))

# ========== دوال مساعدة ==========
def generate_otp():
    return str(random.randint(1000, 9999))

def get_user_by_phone(phone):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    return c.fetchone()

def get_user_by_id(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return c.fetchone()

def get_product(product_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    return c.fetchone()

def get_products(category=None, search=None):
    db = get_db()
    c = db.cursor()
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if category and category != 'all':
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.append(f'%{search}%')
        params.append(f'%{search}%')
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    return c.fetchall()

def is_admin():
    return session.get('is_admin') == True or session.get('admin_unlocked') == True

# ========== المسارات الرئيسية ==========
@app.route('/')
def index():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products ORDER BY created_at DESC LIMIT 6")
    featured = c.fetchall()
    return render_template('index.html', products=featured, app_name=APP_NAME, shop_name=SHOP_NAME)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        user = get_user_by_phone(phone)
        if not user:
            flash('رقم الهاتف غير مسجل. يرجى إنشاء حساب جديد.', 'error')
            return redirect(url_for('register'))
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_phone'] = user['phone']
        flash(f'مرحباً {user["name"]}!', 'success')
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        step = request.form.get('step', '1')
        phone = request.form.get('phone', '').strip()
        if step == '1':
            otp = generate_otp()
            expires = datetime.now() + timedelta(minutes=10)
            db = get_db()
            c = db.cursor()
            c.execute("DELETE FROM otp_codes WHERE phone = ?", (phone,))
            c.execute("INSERT INTO otp_codes (phone, code, expires_at) VALUES (?, ?, ?)", (phone, otp, expires))
            db.commit()
            flash(f'رمز التحقق: {otp}', 'info')
            return redirect(url_for('verify_otp', phone=phone))
        elif step == '2':
            name = request.form.get('name', '').strip()
            password = request.form.get('password', '').strip()
            phone = request.form.get('phone', '').strip()
            referral = request.form.get('referral', '').strip()
            db = get_db()
            c = db.cursor()
            c.execute("SELECT id FROM users WHERE phone = ?", (phone,))
            if c.fetchone():
                flash('رقم الهاتف مسجل مسبقاً', 'error')
                return redirect(url_for('register'))
            referral_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
            c.execute("INSERT INTO users (name, phone, password, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)",
                     (name, phone, password, referral_code, None))
            user_id = c.lastrowid
            if referral:
                c.execute("SELECT id, points FROM users WHERE referral_code = ?", (referral,))
                referrer = c.fetchone()
                if referrer:
                    c.execute("UPDATE users SET referred_by = ? WHERE id = ?", (referrer['id'], user_id))
                    c.execute("UPDATE users SET points = points + 50 WHERE id = ?", (referrer['id'],))
            db.commit()
            session.permanent = True
            session['user_id'] = user_id
            session['user_name'] = name
            session['user_phone'] = phone
            flash('تم إنشاء الحساب بنجاح!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    phone = request.args.get('phone', '')
    if request.method == 'POST':
        phone = request.form.get('phone', '')
        code = request.form.get('code', '')
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM otp_codes WHERE phone = ? AND code = ? AND expires_at > datetime('now') ORDER BY created_at DESC LIMIT 1", (phone, code))
        otp = c.fetchone()
        if otp:
            c.execute("DELETE FROM otp_codes WHERE id = ?", (otp['id'],))
            db.commit()
            return render_template('register.html', phone=phone, step='2')
        else:
            flash('رمز التحقق غير صحيح أو منتهي', 'error')
            return redirect(url_for('verify_otp', phone=phone))
    return render_template('verify_otp.html', phone=phone)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

@app.route('/products')
def products():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    products_list = get_products(category, search)
    categories = ['شاشات', 'بطاريات', 'سماعات', 'كفرات', 'شواحن', 'هواتف']
    return render_template('products.html', products=products_list, categories=categories,
                         current_category=category, search=search, is_admin=is_admin(),
                         reservation_phone=RESERVATION_PHONE)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product(product_id)
    if not product:
        flash('المنتج غير موجود', 'error')
        return redirect(url_for('products'))
    return render_template('product_detail.html', product=product)

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', phone=MAINTENANCE_PHONE)

@app.route('/programming')
def programming():
    return render_template('programming.html', phone=PROGRAMMING_PHONE)

# ========== صفحة الموقع (علامة 📍) ==========
@app.route('/location')
def location():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>موقع المحل - أرين</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            * { margin:0; padding:0; box-sizing:border-box; }
            body {
                font-family:'Cairo',sans-serif;
                background:#000;
                color:#fff;
                min-height:100vh;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                padding:20px;
            }
            .card {
                background:linear-gradient(145deg, #0a0a0a, #111);
                border:1px solid rgba(212,175,55,0.3);
                border-radius:25px;
                padding:40px 30px;
                max-width:400px;
                width:100%;
                text-align:center;
                box-shadow:0 20px 60px rgba(212,175,55,0.15);
                animation: float 3s ease-in-out infinite;
            }
            @keyframes float {
                0%,100% { transform: translateY(0); }
                50% { transform: translateY(-10px); }
            }
            .pin {
                font-size:4rem;
                margin-bottom:15px;
                filter: drop-shadow(0 0 20px rgba(212,175,55,0.5));
            }
            h1 {
                color:#d4af37;
                font-size:1.6rem;
                font-weight:900;
                margin-bottom:10px;
                text-shadow:0 0 15px rgba(212,175,55,0.3);
            }
            .loc {
                color:#aaa;
                font-size:1rem;
                line-height:1.8;
                margin-bottom:25px;
            }
            .loc strong { color:#d4af37; }
            .btn {
                display:block;
                width:100%;
                padding:15px;
                margin-bottom:12px;
                border-radius:15px;
                border:none;
                font-family:'Cairo',sans-serif;
                font-size:1rem;
                font-weight:700;
                cursor:pointer;
                text-decoration:none;
                transition:all 0.3s;
            }
            .btn-maps {
                background:linear-gradient(135deg, #d4af37, #b8941f);
                color:#000;
                box-shadow:0 5px 20px rgba(212,175,55,0.3);
            }
            .btn-maps:hover { transform:scale(1.03); box-shadow:0 8px 30px rgba(212,175,55,0.4); }
            .btn-back {
                background:rgba(255,255,255,0.05);
                color:#888;
                border:1px solid rgba(255,255,255,0.1);
            }
            .btn-back:hover { background:rgba(255,255,255,0.1); color:#fff; }
            .check {
                color:#2ecc71;
                font-weight:700;
                font-size:1.1rem;
                margin-top:5px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="pin">📍</div>
            <h1>""" + SHOP_NAME + """</h1>
            <div class="loc">
                <strong>موقعنا:</strong><br>
                المهرة - الغيضة<br>
                الهنجر - سوق بن خودم<br>
                <span class="check">✅ خيارك الأفضل 🤍</span>
            </div>
            <a href="https://maps.google.com/?q=14.1044,47.7697" class="btn btn-maps" target="_blank">
                🗺️ موقعنا على الخريطة
            </a>
            <a href="javascript:history.back()" class="btn btn-back">🔙 رجوع</a>
        </div>
    </body>
    </html>
    """

# ========== نقاط الولاء ==========
@app.route('/loyalty')
def loyalty():
    if 'user_id' not in session:
        flash('يرجى تسجيل الدخول أولاً', 'warning')
        return redirect(url_for('login'))
    user = get_user_by_id(session['user_id'])
    rewards = {100:'صيانة مجانية', 200:'خصم 20%', 300:'كفر حماية', 500:'سماعة', 800:'شاحن', 1000:'شاشة'}
    return render_template('loyalty.html', user=user, rewards=rewards)

# ========== أجهزتي ==========
@app.route('/my_devices', methods=['GET', 'POST'])
def my_devices():
    if 'user_id' not in session:
        flash('يرجى تسجيل الدخول أولاً', 'warning')
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    if request.method == 'POST':
        device_name = request.form.get('device_name')
        part_name = request.form.get('part_name')
        purchase_date = request.form.get('purchase_date')
        warranty_months = request.form.get('warranty_months', 0)
        c.execute("INSERT INTO user_devices (user_id, device_name, part_name, purchase_date, warranty_months) VALUES (?, ?, ?, ?, ?)",
                 (session['user_id'], device_name, part_name, purchase_date, warranty_months))
        c.execute("UPDATE users SET points = points + 5 WHERE id = ?", (session['user_id'],))
        db.commit()
        flash('تم إضافة الجهاز بنجاح! +5 نقاط', 'success')
        return redirect(url_for('my_devices'))
    c.execute("SELECT * FROM user_devices WHERE user_id = ?", (session['user_id'],))
    devices = c.fetchall()
    return render_template('my_devices.html', devices=devices)

@app.route('/delete_device/<int:device_id>', methods=['POST'])
def delete_device(device_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM user_devices WHERE id = ? AND user_id = ?", (device_id, session['user_id']))
    db.commit()
    flash('تم حذف الجهاز', 'success')
    return redirect(url_for('my_devices'))

# ========== إشعارات ==========
@app.route('/notify_me', methods=['POST'])
def notify_me():
    if 'user_id' not in session:
        flash('يرجى تسجيل الدخول أولاً', 'warning')
        return redirect(url_for('login'))
    product_name = request.form.get('product_name')
    phone = session.get('user_phone', '')
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO alerts (user_id, product_name, phone) VALUES (?, ?, ?)", (session['user_id'], product_name, phone))
    db.commit()
    flash('سنخبرك عند توفر المنتج!', 'success')
    return redirect(url_for('products'))

# ========== لوحة تحكم الأدمن ==========
@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password', '')
    if password == ADMIN_PASSWORD:
        session['admin_unlocked'] = True
        session.permanent = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'كلمة السر غير صحيحة'}), 401

@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_admin():
        flash('غير مصرح', 'error')
        return redirect(url_for('index'))
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) as total FROM users")
    total_users = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM products")
    total_products = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM reservations WHERE status = 'pending'")
    pending_reservations = c.fetchone()['total']
    try:
        return render_template('admin/dashboard.html', total_users=total_users, total_products=total_products, pending_reservations=pending_reservations)
    except:
        # fallback HTML لو القالب غير موجود
        return f"""
        <!DOCTYPE html>
        <html dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{ background:#000; color:#fff; font-family:'Cairo',sans-serif; padding:20px; }}
            .box {{ background:#0a0a0a; border:1px solid rgba(212,175,55,0.3); border-radius:20px; padding:30px; margin:20px 0; }}
            h1 {{ color:#d4af37; }}
            .stat {{ display:inline-block; background:#111; border:1px solid rgba(212,175,55,0.2); border-radius:15px; padding:20px; margin:10px; min-width:150px; text-align:center; }}
            .num {{ font-size:2rem; color:#d4af37; font-weight:900; }}
            a {{ color:#d4af37; text-decoration:none; display:block; margin:10px 0; }}
        </style></head><body>
        <h1>👑 لوحة تحكم {APP_NAME}</h1>
        <div class="box">
            <div class="stat"><div class="num">{total_users}</div><div>المستخدمين</div></div>
            <div class="stat"><div class="num">{total_products}</div><div>المنتجات</div></div>
            <div class="stat"><div class="num">{pending_reservations}</div><div>حجوزات معلقة</div></div>
        </div>
        <div class="box">
            <a href="/admin/products">📦 إدارة المنتجات</a>
            <a href="/admin/reservations">📋 إدارة الحجوزات</a>
            <a href="/">🏠 العودة للموقع</a>
        </div>
        </body></html>
        """

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if not is_admin():
        flash('غير مصرح', 'error')
        return redirect(url_for('index'))
    db = get_db()
    c = db.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        original_price = request.form.get('original_price', 0)
        image = request.form.get('image', '')
        description = request.form.get('description', '')
        category = request.form.get('category')
        stock = request.form.get('stock', 0)
        status = request.form.get('status', 'available')
        is_rare = 1 if request.form.get('is_rare') else 0
        currency = request.form.get('currency', 'ر.ي')
        c.execute("INSERT INTO products (name, price, original_price, image, description, category, stock, status, is_rare, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (name, price, original_price, image, description, category, stock, status, is_rare, currency))
        c.execute("SELECT id FROM users")
        users = c.fetchall()
        for user in users:
            c.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                     (user['id'], 'منتج جديد!', f'تم إضافة {name} إلى المتجر'))
        db.commit()
        flash('تم إضافة المنتج بنجاح', 'success')
        return redirect(url_for('admin_products'))
    c.execute("SELECT * FROM products ORDER BY created_at DESC")
    products_list = c.fetchall()
    return render_template('admin/products.html', products=products_list)

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash('تم حذف المنتج', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/reservations')
def admin_reservations():
    if not is_admin():
        flash('غير مصرح', 'error')
        return redirect(url_for('index'))
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT r.*, p.name as product_name, p.price, p.currency, u.name as user_name
        FROM reservations r
        LEFT JOIN products p ON r.product_id = p.id
        LEFT JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """)
    reservations = c.fetchall()
    return render_template('admin/reservations.html', reservations=reservations)

@app.route('/admin/confirm_reservation/<int:reservation_id>', methods=['POST'])
def confirm_reservation(reservation_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    reservation = c.fetchone()
    if reservation:
        c.execute("UPDATE reservations SET status = 'confirmed' WHERE id = ?", (reservation_id,))
        c.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (reservation['product_id'],))
        c.execute("UPDATE users SET points = points + 20 WHERE id = ?", (reservation['user_id'],))
        c.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                 (reservation['user_id'], 'تم تأكيد الحجز', 'تم تأكيد حجزك بنجاح! +20 نقطة'))
        db.commit()
        flash('تم تأكيد الحجز', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/cancel_reservation/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))
    c.execute("SELECT user_id FROM reservations WHERE id = ?", (reservation_id,))
    res = c.fetchone()
    if res:
        c.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                 (res['user_id'], 'تم إلغاء الحجز', 'نعتذر، تم إلغاء حجزك'))
    db.commit()
    flash('تم إلغاء الحجز', 'info')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/delete_reservation/<int:reservation_id>', methods=['POST'])
def delete_reservation(reservation_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    db.commit()
    flash('تم حذف الحجز نهائياً', 'success')
    return redirect(url_for('admin_reservations'))

# ========== API الحجز الجديد ==========
@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'يرجى تسجيل الدخول أولاً'}), 401
    data = request.get_json() or request.form
    product_id = data.get('product_id')
    customer_name = data.get('customer_name', session.get('user_name', 'عميل'))
    phone = data.get('phone', session.get('user_phone', ''))
    if not product_id:
        return jsonify({'success': False, 'error': 'معرف المنتج مطلوب'}), 400
    product = get_product(product_id)
    if not product:
        return jsonify({'success': False, 'error': 'المنتج غير موجود'}), 404
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO reservations (user_id, product_id, customer_name, phone, status) VALUES (?, ?, ?, ?, ?)",
                 (session['user_id'], product_id, customer_name, phone, 'pending'))
        db.commit()
        return jsonify({'success': True, 'message': 'تم إنشاء الحجز بنجاح!', 'reservation_id': c.lastrowid, 'status': 'pending'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservation_whatsapp/<int:reservation_id>')
def reservation_whatsapp(reservation_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT r.*, p.name as product_name, p.price, p.currency FROM reservations r LEFT JOIN products p ON r.product_id = p.id WHERE r.id = ?", (reservation_id,))
    reservation = c.fetchone()
    if not reservation:
        flash('الحجز غير موجود', 'error')
        return redirect(url_for('products'))
    message = f"""مرحباً بدر الحضرمي،\nأرغب في حجز المنتج التالي:\n🏷️ المنتج: {reservation['product_name']}\n💰 السعر: {reservation['price']} {reservation['currency']}\n👤 الاسم: {reservation['customer_name']}\n📱 الرقم: {reservation['phone']}\n🆔 رقم الحجز: #{reservation_id}\n"""
    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/967{RESERVATION_PHONE}?text={encoded_msg}"
    return redirect(whatsapp_url)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
