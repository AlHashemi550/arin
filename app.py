import os
import sqlite3
import random
import string
import traceback
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

app = Flask(__name__)
app.secret_key = 'arin_secret_key_2024'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)

APP_NAME = 'أرين'
SHOP_NAME = 'محل الراشد للجوالات'
SHOP_LOCATION = 'المهرة - الغيضة - الهنجر - سوق بن خودم'
ADMIN_PHONES = ['783234925', '779505979', '773852062']
ADMIN_PASSWORD = '78323'
RESERVATION_PHONE = '773852062'
MAINTENANCE_PHONE = '779505979'
PROGRAMMING_PHONE = '783234925'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'laqta.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    try:
        db = get_db()
        tables = [
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password TEXT,
                points INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                referral_code TEXT,
                referred_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                original_price REAL,
                image TEXT,
                description TEXT,
                category TEXT,
                stock INTEGER DEFAULT 0,
                status TEXT DEFAULT 'available',
                is_rare INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'ر.ي',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                customer_name TEXT,
                phone TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS user_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                device_name TEXT,
                part_name TEXT,
                purchase_date TEXT,
                warranty_months INTEGER,
                last_notified TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_name TEXT,
                phone TEXT,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                code TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        for table in tables:
            db.execute(table)
        db.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_phone' not in session:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('login'))
        phone = session['user_phone'].replace('+967', '').replace('967', '').lstrip('0')
        if phone not in ADMIN_PHONES:
            flash('غير مصرح', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    try:
        get_db()
    except Exception as e:
        print(f"DB Error: {e}")

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="خطأ في السيرفر", shop_location=SHOP_LOCATION), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="الصفحة غير موجودة", shop_location=SHOP_LOCATION), 404

@app.route('/')
def index():
    try:
        db = get_db()
        products = db.execute('SELECT * FROM products WHERE status = "available" ORDER BY created_at DESC LIMIT 6').fetchall()
        return render_template('index.html', products=products, app_name=APP_NAME, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"Index Error: {e}")
        return render_template('index.html', products=[], app_name=APP_NAME, shop_location=SHOP_LOCATION)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        admin_pass = request.form.get('admin_password', '').strip()
        clean_phone = phone.replace('+967', '').replace('967', '').lstrip('0')
        
        try:
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE phone = ?', (clean_phone,)).fetchone()
            
            # ✅ إذا رقم أدمن - تحقق من باسورد الأدمن فقط
            if clean_phone in ADMIN_PHONES:
                if admin_pass != ADMIN_PASSWORD:
                    flash('باسورد الأدمن غير صحيح', 'error')
                    return redirect(url_for('login'))
                
                # الأدمن موجود في قاعدة البيانات؟
                if not user:
                    # إنشاء حساب أدمن تلقائياً إذا مو موجود
                    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    db.execute('''INSERT INTO users (name, phone, password, points, is_admin, referral_code)
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                              ('أدمن', clean_phone, ADMIN_PASSWORD, 0, 1, referral_code))
                    db.commit()
                    user = db.execute('SELECT * FROM users WHERE phone = ?', (clean_phone,)).fetchone()
                
                session.permanent = True
                session['user_id'] = user['id']
                session['user_phone'] = clean_phone
                session['user_name'] = user['name']
                session['is_admin'] = True
                flash('تم تسجيل الدخول كأدمن', 'success')
                return redirect(url_for('admin_dashboard'))
            
            # ✅ إذا مو أدمن - تحقق من الباسورد العادي
            if not user:
                flash('رقم الهاتف غير مسجل', 'error')
                return redirect(url_for('login'))
            
            if user['password'] and user['password'] != password:
                flash('كلمة المرور غير صحيحة', 'error')
                return redirect(url_for('login'))
            
            session.permanent = True
            session['user_id'] = user['id']
            session['user_phone'] = clean_phone
            session['user_name'] = user['name']
            session['is_admin'] = False
            
            return redirect(url_for('products'))
            
        except Exception as e:
            print(f"Login Error: {e}")
            traceback.print_exc()
            flash('حدث خطأ، حاول مرة أخرى', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html', shop_location=SHOP_LOCATION)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        clean_phone = phone.replace('+967', '').replace('967', '').lstrip('0')
        
        if len(clean_phone) < 9:
            flash('رقم الهاتف غير صحيح', 'error')
            return redirect(url_for('register'))
        
        try:
            db = get_db()
            existing = db.execute('SELECT * FROM users WHERE phone = ?', (clean_phone,)).fetchone()
            if existing:
                flash('رقم الهاتف مسجل مسبقاً', 'error')
                return redirect(url_for('register'))
            
            otp = ''.join(random.choices(string.digits, k=4))
            expires = datetime.now() + timedelta(minutes=10)
            
            db.execute('DELETE FROM otp_codes WHERE phone = ?', (clean_phone,))
            db.execute('INSERT INTO otp_codes (phone, code, expires_at) VALUES (?, ?, ?)', 
                       (clean_phone, otp, expires))
            db.commit()
            
            session['reg_phone'] = clean_phone
            return redirect(url_for('otp_sent'))
        except Exception as e:
            print(f"Register Error: {e}")
            flash('حدث خطأ في التسجيل', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html', shop_location=SHOP_LOCATION)

@app.route('/otp_sent')
def otp_sent():
    if 'reg_phone' not in session:
        return redirect(url_for('register'))
    
    try:
        db = get_db()
        otp_record = db.execute('SELECT * FROM otp_codes WHERE phone = ?', 
                               (session['reg_phone'],)).fetchone()
        if not otp_record:
            flash('انتهت صلاحية الكود', 'error')
            return redirect(url_for('register'))
        
        otp = otp_record['code']
        phone = session['reg_phone']
        message = f"كود التحقق من أرين: {otp}\\nلا تشاركه مع أحد."
        whatsapp_url = f"https://wa.me/967{phone}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
        
        return render_template('otp_sent.html', otp=otp, phone=phone, 
                               whatsapp_url=whatsapp_url, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"OTP Sent Error: {e}")
        flash('حدث خطأ', 'error')
        return redirect(url_for('register'))

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reg_phone' not in session:
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()
        referral = request.form.get('referral', '').strip()
        
        try:
            db = get_db()
            otp_record = db.execute('SELECT * FROM otp_codes WHERE phone = ? AND code = ?',
                                   (session['reg_phone'], code)).fetchone()
            
            if not otp_record:
                flash('رمز التحقق غير صحيح', 'error')
                return redirect(url_for('verify_otp'))
            
            # ✅ إصلاح مقارنة التاريخ
            expires_at = otp_record['expires_at']
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    try:
                        expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            if datetime.now() > expires_at:
                flash('رمز التحقق منتهي الصلاحية', 'error')
                return redirect(url_for('register'))
            
            referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            db.execute('''INSERT INTO users (name, phone, password, points, referral_code, referred_by)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (name, session['reg_phone'], password, 0, referral_code, referral or None))
            
            if referral:
                referrer = db.execute('SELECT * FROM users WHERE referral_code = ?', (referral,)).fetchone()
                if referrer:
                    db.execute('UPDATE users SET points = points + 50 WHERE id = ?', (referrer['id'],))
            
            db.execute('DELETE FROM otp_codes WHERE phone = ?', (session['reg_phone'],))
            db.commit()
            
            user = db.execute('SELECT * FROM users WHERE phone = ?', (session['reg_phone'],)).fetchone()
            session.permanent = True
            session['user_id'] = user['id']
            session['user_phone'] = user['phone']
            session['user_name'] = user['name']
            session['is_admin'] = user['phone'] in ADMIN_PHONES
            
            session.pop('reg_phone', None)
            flash('تم التسجيل بنجاح!', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            print(f"Verify OTP Error: {e}")
            traceback.print_exc()
            flash('حدث خطأ أثناء التسجيل النهائي', 'error')
            return redirect(url_for('register'))
    
    return render_template('verify_otp.html', shop_location=SHOP_LOCATION)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

@app.route('/products')
def products():
    try:
        db = get_db()
        category = request.args.get('category', '')
        search = request.args.get('search', '')
        
        query = 'SELECT * FROM products WHERE 1=1'
        params = []
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        if search:
            query += ' AND (name LIKE ? OR description LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        query += ' ORDER BY created_at DESC'
        products = db.execute(query, params).fetchall()
        categories = db.execute('SELECT DISTINCT category FROM products').fetchall()
        
        return render_template('products.html', products=products, categories=categories, 
                             current_category=category, search=search, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"Products Error: {e}")
        traceback.print_exc()
        return render_template('products.html', products=[], categories=[], 
                             current_category='', search='', shop_location=SHOP_LOCATION)

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', phone=MAINTENANCE_PHONE, shop_location=SHOP_LOCATION)

@app.route('/programming')
def programming():
    return render_template('programming.html', phone=PROGRAMMING_PHONE, shop_location=SHOP_LOCATION)

@app.route('/loyalty')
def loyalty():
    if 'user_id' not in session:
        flash('يجب تسجيل الدخول', 'error')
        return redirect(url_for('login'))
    
    try:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        rewards = [
            {'points': 100, 'reward': 'صيانة مجانية'},
            {'points': 200, 'reward': 'خصم 20%'},
            {'points': 300, 'reward': 'كفر حماية'},
            {'points': 500, 'reward': 'سماعة'},
            {'points': 800, 'reward': 'شاحن'},
            {'points': 1000, 'reward': 'شاشة'}
        ]
        return render_template('loyalty.html', user=user, rewards=rewards, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"Loyalty Error: {e}")
        return redirect(url_for('index'))

@app.route('/my_devices')
def my_devices():
    if 'user_id' not in session:
        flash('يجب تسجيل الدخول', 'error')
        return redirect(url_for('login'))
    
    try:
        db = get_db()
        devices = db.execute('SELECT * FROM user_devices WHERE user_id = ?', 
                            (session['user_id'],)).fetchall()
        return render_template('my_devices.html', devices=devices, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"My Devices Error: {e}")
        return render_template('my_devices.html', devices=[], shop_location=SHOP_LOCATION)

@app.route('/add_device', methods=['POST'])
def add_device():
    if 'user_id' not in session:
        return jsonify({'error': 'يجب تسجيل الدخول'}), 401
    
    try:
        db = get_db()
        db.execute('''INSERT INTO user_devices 
                     (user_id, device_name, part_name, purchase_date, warranty_months)
                     VALUES (?, ?, ?, ?, ?)''',
                  (session['user_id'], request.form['device_name'], request.form['part_name'],
                   request.form['purchase_date'], int(request.form['warranty_months'])))
        
        db.execute('UPDATE users SET points = points + 5 WHERE id = ?', (session['user_id'],))
        db.commit()
        flash('تم إضافة الجهاز بنجاح', 'success')
    except Exception as e:
        print(f"Add Device Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('my_devices'))

@app.route('/delete_device/<int:id>', methods=['POST'])
def delete_device(id):
    if 'user_id' not in session:
        return jsonify({'error': 'يجب تسجيل الدخول'}), 401
    
    try:
        db = get_db()
        db.execute('DELETE FROM user_devices WHERE id = ? AND user_id = ?', 
                  (id, session['user_id']))
        db.commit()
        flash('تم حذف الجهاز', 'info')
    except Exception as e:
        print(f"Delete Device Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('my_devices'))

@app.route('/reserve', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        flash('يجب تسجيل الدخول', 'error')
        return redirect(url_for('login'))
    
    try:
        product_id = request.form.get('product_id')
        db = get_db()
        product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        
        if not product or product['stock'] <= 0:
            flash('المنتج غير متوفر', 'error')
            return redirect(url_for('products'))
        
        db.execute('''INSERT INTO reservations 
                     (user_id, product_id, customer_name, phone, status)
                     VALUES (?, ?, ?, ?, ?)''',
                  (session['user_id'], product_id, session.get('user_name', ''), 
                   session['user_phone'], 'pending'))
        db.commit()
        
        message = f"حجز جديد من تطبيق أرين:\\nالعميل: {session.get('user_name', '')}\\nالهاتف: {session['user_phone']}\\nالمنتج: {product['name']}"
        whatsapp_url = f"https://wa.me/967{RESERVATION_PHONE}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
        
        flash('تم إرسال الحجز، سيتم التواصل معك', 'success')
        return redirect(whatsapp_url)
    except Exception as e:
        print(f"Reserve Error: {e}")
        flash('حدث خطأ في الحجز', 'error')
        return redirect(url_for('products'))

@app.route('/notify_me', methods=['POST'])
def notify_me():
    if 'user_id' not in session:
        flash('يجب تسجيل الدخول', 'error')
        return redirect(url_for('login'))
    
    try:
        product_name = request.form.get('product_name')
        db = get_db()
        db.execute('INSERT INTO alerts (user_id, product_name, phone) VALUES (?, ?, ?)',
                  (session['user_id'], product_name, session['user_phone']))
        db.commit()
        flash('سنبلغك عند توفر المنتج', 'success')
    except Exception as e:
        print(f"Notify Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('products'))

@app.route('/whatsapp_redirect')
def whatsapp_redirect():
    service = request.args.get('service', '')
    phone = request.args.get('phone', '')
    device = request.args.get('device', '')
    
    name = session.get('user_name', 'عميل')
    user_phone = session.get('user_phone', '')
    
    message = f"طلب خدمة من تطبيق أرين:\\nالعميل: {name}\\nالهاتف: {user_phone}\\nالخدمة: {service}\\nالجهاز: {device}"
    url = f"https://wa.me/967{phone}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
    return redirect(url)

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    try:
        db = get_db()
        stats = {
            'products': db.execute('SELECT COUNT(*) as c FROM products').fetchone()['c'],
            'reservations': db.execute('SELECT COUNT(*) as c FROM reservations WHERE status = "pending"').fetchone()['c'],
            'users': db.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
        }
        return render_template('admin/dashboard.html', stats=stats, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"Admin Error: {e}")
        return render_template('admin/dashboard.html', stats={'products':0,'reservations':0,'users':0}, shop_location=SHOP_LOCATION)

@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def admin_products():
    db = get_db()
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            price = float(request.form['price'])
            original_price = request.form.get('original_price') or None
            if original_price:
                original_price = float(original_price)
            description = request.form.get('description', '')
            category = request.form['category']
            stock = int(request.form['stock'])
            currency = request.form.get('currency', 'ر.ي')
            is_rare = 1 if request.form.get('is_rare') else 0
            
            image = request.files.get('image')
            image_path = ''
            if image and image.filename:
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
                image.save(os.path.join(UPLOAD_FOLDER, filename))
                image_path = f'uploads/{filename}'
            
            db.execute('''INSERT INTO products 
                         (name, price, original_price, image, description, category, stock, currency, is_rare)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (name, price, original_price, image_path, description, category, stock, currency, is_rare))
            db.commit()
            flash('تم إضافة المنتج بنجاح', 'success')
        except Exception as e:
            print(f"Add Product Error: {e}")
            flash('حدث خطأ في إضافة المنتج', 'error')
    
    try:
        products = db.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    except:
        products = []
    return render_template('admin/products.html', products=products, shop_location=SHOP_LOCATION)

@app.route('/admin/delete_product/<int:id>', methods=['POST'])
@admin_required
def delete_product(id):
    try:
        db = get_db()
        db.execute('DELETE FROM products WHERE id = ?', (id,))
        db.commit()
        flash('تم حذف المنتج', 'info')
    except Exception as e:
        print(f"Delete Product Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('admin_products'))

@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    try:
        db = get_db()
        reservations = db.execute('''SELECT r.*, p.name as product_name, u.name as user_name 
                                    FROM reservations r
                                    LEFT JOIN products p ON r.product_id = p.id
                                    LEFT JOIN users u ON r.user_id = u.id
                                    ORDER BY r.created_at DESC''').fetchall()
        return render_template('admin/reservations.html', reservations=reservations, shop_location=SHOP_LOCATION)
    except Exception as e:
        print(f"Reservations Error: {e}")
        return render_template('admin/reservations.html', reservations=[], shop_location=SHOP_LOCATION)

@app.route('/admin/confirm_reservation/<int:id>', methods=['POST'])
@admin_required
def confirm_reservation(id):
    try:
        db = get_db()
        res = db.execute('SELECT * FROM reservations WHERE id = ?', (id,)).fetchone()
        
        if res:
            db.execute('UPDATE reservations SET status = ? WHERE id = ?', ('confirmed', id))
            db.execute('UPDATE products SET stock = stock - 1 WHERE id = ?', (res['product_id'],))
            db.execute('UPDATE users SET points = points + 20 WHERE id = ?', (res['user_id'],))
            db.commit()
            
            message = f"تم تأكيد حجزك في أرين!\\nالمنتج: {res['product_name']}\\nشكراً لثقتك بنا."
            url = f"https://wa.me/967{res['phone']}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
            return redirect(url)
    except Exception as e:
        print(f"Confirm Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/cancel_reservation/<int:id>', methods=['POST'])
@admin_required
def cancel_reservation(id):
    try:
        db = get_db()
        res = db.execute('SELECT * FROM reservations WHERE id = ?', (id,)).fetchone()
        
        if res:
            db.execute('UPDATE reservations SET status = ? WHERE id = ?', ('cancelled', id))
            db.commit()
            
            message = f"نعتذر، تم إلغاء حجزك في أرين.\\nللاستفسار تواصل معنا."
            url = f"https://wa.me/967{res['phone']}?text={message.replace(' ', '%20').replace(chr(10), '%0A')}"
            return redirect(url)
    except Exception as e:
        print(f"Cancel Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/delete_reservation/<int:id>', methods=['POST'])
@admin_required
def delete_reservation(id):
    try:
        db = get_db()
        db.execute('DELETE FROM reservations WHERE id = ?', (id,))
        db.commit()
        flash('تم حذف الحجز نهائياً', 'info')
    except Exception as e:
        print(f"Delete Reservation Error: {e}")
        flash('حدث خطأ', 'error')
    return redirect(url_for('admin_reservations'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
