import os
import sqlite3
import random
import string
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'areen_secret_key_2026_mohammed_alhashmi'
app.permanent_session_lifetime = datetime.timedelta(days=365)

# ==================== CONFIG ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'laqta.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ADMIN_PASSWORD = '78323'
RESERVATION_PHONE = '773852062'
MAINTENANCE_PHONE = '779505979'
PROGRAMMING_PHONE = '783234925'
APP_NAME = 'أرين'
SHOP_NAME = 'محل الراشد للجوالات'
SHOP_LOCATION = 'المهرة - الغيضة - الهنجر - سوق بن خودم'

# ==================== DATABASE ====================
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, phone TEXT UNIQUE, password TEXT,
            points INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0, block_reason TEXT,
            referral_code TEXT, referred_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, price REAL, original_price REAL,
            image TEXT, description TEXT, category TEXT,
            stock INTEGER DEFAULT 1, status TEXT DEFAULT 'available',
            is_rare INTEGER DEFAULT 0, currency TEXT DEFAULT 'ر.ي',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, product_id INTEGER,
            customer_name TEXT, phone TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS blocked_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE, name TEXT,
            reason TEXT, blocked_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    db.commit()

# ==================== HELPERS ====================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('يجب تسجيل الدخول كأدمن', 'warning')
            return redirect('/products')
        return f(*args, **kwargs)
    return decorated_function

def check_blocked(phone):
    db = get_db()
    blocked = db.execute("SELECT * FROM blocked_customers WHERE phone = ?", (phone,)).fetchone()
    return blocked

def get_image_url(image_path):
    """إرجاع مسار الصورة الصحيح - مبسطة وآمنة"""
    if not image_path or image_path == 'default.jpg' or image_path == '':
        return '/static/uploads/default.jpg'
    
    # إذا كان المسار يبدأ بـ /
    if image_path.startswith('/'):
        return image_path
    
    # إذا كان المسار يبدأ بـ uploads/
    if image_path.startswith('uploads/'):
        return '/static/' + image_path
    
    # إذا كان المسار يبدأ بـ static/
    if image_path.startswith('static/'):
        return '/' + image_path
    
    # إذا كان اسم الملف فقط
    if '/' not in image_path:
        return '/static/uploads/' + image_path
    
    # أي حالة أخرى
    return '/static/uploads/' + image_path

def save_image(file):
    """حفظ الصورة وإرجاع المسار"""
    if not file or not file.filename:
        return 'default.jpg'
    
    try:
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
            return 'default.jpg'
        
        filename = f"prod_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return f"uploads/{filename}"
    except Exception:
        return 'default.jpg'

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def splash():
    return render_template('splash.html')

@app.route('/products')
def products():
    try:
        db = get_db()
        category = request.args.get('category', 'all')
        search = request.args.get('search', '').strip()
        currency_filter = request.args.get('currency', 'all')
        
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        if category != 'all':
            query += " AND category = ?"
            params.append(category)
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.append(f'%{search}%')
            params.append(f'%{search}%')
        if currency_filter != 'all':
            query += " AND currency = ?"
            params.append(currency_filter)
        
        query += " ORDER BY created_at DESC"
        products = db.execute(query, params).fetchall()
        
        cats = db.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL").fetchall()
        categories = [c['category'] for c in cats if c['category']]
        
        curr = db.execute("SELECT DISTINCT currency FROM products WHERE currency IS NOT NULL").fetchall()
        currencies = [c['currency'] for c in curr if c['currency']]
        
        return render_template('products.html', 
                             products=products, 
                             categories=categories,
                             currencies=currencies,
                             current_category=category,
                             current_currency=currency_filter,
                             search=search,
                             is_admin=session.get('is_admin'),
                             shop_name=SHOP_NAME,
                             get_image_url=get_image_url)
    except Exception as e:
        flash(f'خطأ في تحميل المنتجات: {str(e)}', 'error')
        return render_template('products.html', 
                             products=[], 
                             categories=[],
                             currencies=[],
                             current_category='all',
                             current_currency='all',
                             search='',
                             is_admin=session.get('is_admin'),
                             shop_name=SHOP_NAME,
                             get_image_url=get_image_url)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    try:
        db = get_db()
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            flash('المنتج غير موجود', 'error')
            return redirect(url_for('products'))
        
        related = db.execute(
            "SELECT * FROM products WHERE category = ? AND id != ? LIMIT 4",
            (product['category'], product_id)
        ).fetchall()
        
        return render_template('product_detail.html', 
                             product=product, 
                             related=related,
                             is_admin=session.get('is_admin'),
                             reservation_phone=RESERVATION_PHONE,
                             get_image_url=get_image_url)
    except Exception as e:
        flash(f'خطأ في تحميل المنتج: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/reserve', methods=['POST'])
def reserve():
    try:
        db = get_db()
        product_id = request.form.get('product_id')
        customer_name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # التحقق من الحظر
        blocked = check_blocked(phone)
        if blocked:
            flash(f'⛔ عذراً، هذا الرقم محظور. السبب: {blocked["reason"]}', 'error')
            return redirect(url_for('product_detail', product_id=product_id))
        
        if not all([product_id, customer_name, phone]):
            flash('يرجى إدخال الاسم ورقم الهاتف', 'error')
            return redirect(url_for('product_detail', product_id=product_id))
        
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            flash('المنتج غير موجود', 'error')
            return redirect(url_for('products'))
        
        if product['stock'] <= 0:
            flash('عذراً، هذا المنتج غير متوفر حالياً', 'error')
            return redirect(url_for('product_detail', product_id=product_id))
        
        db.execute('''
            INSERT INTO reservations (product_id, customer_name, phone, status)
            VALUES (?, ?, ?, 'pending')
        ''', (product_id, customer_name, phone))
        
        db.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (product_id,))
        db.commit()
        
        # بناء رسالة واتساب بشكل صحيح
        res_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        msg = f"مرحباً {APP_NAME} 👋\n\n"
        msg += f"أريد حجز المنتج التالي:\n"
        msg += f"📱 *{product['name']}*\n"
        msg += f"💰 السعر: *{product['price']} {product['currency']}*\n"
        msg += f"👤 العميل: *{customer_name}*\n"
        msg += f"📞 الهاتف: *{phone}*\n"
        msg += f"📦 رقم الطلب: #{res_id}\n\n"
        msg += f"🏬 {SHOP_NAME}\n📍 {SHOP_LOCATION}"
        
        # ترميز الرسالة للرابط
        import urllib.parse
        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/967{RESERVATION_PHONE}?text={encoded_msg}"
        
        flash('تم إرسال طلبك، سيتم توجيهك لواتساب العامل', 'success')
        return redirect(wa_url)
        
    except Exception as e:
        flash(f'خطأ في إنشاء الحجز: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', 
                         maintenance_phone=MAINTENANCE_PHONE,
                         shop_name=SHOP_NAME)

@app.route('/programming')
def programming():
    return render_template('programming.html', 
                         programming_phone=PROGRAMMING_PHONE,
                         shop_name=SHOP_NAME)

@app.route('/loyalty')
def loyalty():
    return render_template('loyalty.html', shop_name=SHOP_NAME)

@app.route('/my_devices')
def my_devices():
    return render_template('my_devices.html', shop_name=SHOP_NAME)

# ==================== ADMIN ROUTES ====================

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    try:
        password = request.form.get('password', '').strip()
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session.permanent = True
            return jsonify({'success': True})
        else:
            return jsonify({'success': False}), 403
    except Exception:
        return jsonify({'success': False}), 500

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect('/products')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        db = get_db()
        stats = {
            'total_products': db.execute("SELECT COUNT(*) as c FROM products").fetchone()['c'],
            'total_reservations': db.execute("SELECT COUNT(*) as c FROM reservations").fetchone()['c'],
            'pending_reservations': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='pending'").fetchone()['c'],
            'confirmed_reservations': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='confirmed'").fetchone()['c'],
            'cancelled_reservations': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='cancelled'").fetchone()['c'],
            'low_stock': db.execute("SELECT COUNT(*) as c FROM products WHERE stock <= 2").fetchone()['c'],
            'blocked_customers': db.execute("SELECT COUNT(*) as c FROM blocked_customers").fetchone()['c']
        }
        
        recent_reservations = db.execute('''
            SELECT r.*, p.name as product_name, p.price, p.currency
            FROM reservations r
            JOIN products p ON r.product_id = p.id
            ORDER BY r.created_at DESC LIMIT 10
        ''').fetchall()
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             reservations=recent_reservations,
                             shop_name=SHOP_NAME)
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect('/products')

@app.route('/admin/products')
@admin_required
def admin_products():
    try:
        db = get_db()
        products = db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
        return render_template('admin/products.html', 
                             products=products,
                             shop_name=SHOP_NAME,
                             get_image_url=get_image_url)
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect('/admin/dashboard')

@app.route('/admin/product/add', methods=['POST'])
@admin_required
def add_product():
    try:
        db = get_db()
        
        name = request.form.get('name', '').strip()
        price = request.form.get('price', 0)
        original_price = request.form.get('original_price', 0)
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        stock = request.form.get('stock', 1)
        currency = request.form.get('currency', 'ر.ي')
        is_rare = 1 if request.form.get('is_rare') else 0
        
        # حفظ الصورة
        image = 'default.jpg'
        if 'image' in request.files:
            image = save_image(request.files['image'])
        elif 'image_camera' in request.files:
            image = save_image(request.files['image_camera'])
        
        db.execute('''
            INSERT INTO products (name, price, original_price, image, description, category, stock, currency, is_rare)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, price, original_price, image, description, category, stock, currency, is_rare))
        db.commit()
        
        flash('✅ تم إضافة المنتج بنجاح', 'success')
    except Exception as e:
        flash(f'خطأ في إضافة المنتج: {str(e)}', 'error')
    
    return redirect(url_for('admin_products'))

@app.route('/admin/product/delete/<int:product_id>')
@admin_required
def delete_product(product_id):
    try:
        db = get_db()
        db.execute("DELETE FROM reservations WHERE product_id = ?", (product_id,))
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()
        flash('🗑️ تم حذف المنتج نهائياً', 'success')
    except Exception as e:
        flash(f'خطأ في الحذف: {str(e)}', 'error')
    return redirect(url_for('admin_products'))

@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    try:
        db = get_db()
        status_filter = request.args.get('status', 'all')
        
        query = '''
            SELECT r.*, p.name as product_name, p.price, p.currency, p.image, p.stock
            FROM reservations r
            JOIN products p ON r.product_id = p.id
            WHERE 1=1
        '''
        params = []
        
        if status_filter != 'all':
            query += " AND r.status = ?"
            params.append(status_filter)
        
        query += " ORDER BY r.created_at DESC"
        reservations = db.execute(query, params).fetchall()
        
        stats = {
            'pending': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='pending'").fetchone()['c'],
            'confirmed': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='confirmed'").fetchone()['c'],
            'cancelled': db.execute("SELECT COUNT(*) as c FROM reservations WHERE status='cancelled'").fetchone()['c']
        }
        
        return render_template('admin/reservations.html', 
                             reservations=reservations,
                             stats=stats,
                             current_status=status_filter,
                             shop_name=SHOP_NAME,
                             get_image_url=get_image_url)
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect('/admin/dashboard')

@app.route('/admin/reservation/confirm/<int:res_id>')
@admin_required
def confirm_reservation(res_id):
    try:
        db = get_db()
        res = db.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)).fetchone()
        
        if res:
            db.execute("UPDATE reservations SET status = 'confirmed' WHERE id = ?", (res_id,))
            db.commit()
            flash('تم تأكيد الحجز بنجاح', 'success')
        
        return redirect(url_for('admin_reservations'))
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect(url_for('admin_reservations'))

@app.route('/admin/reservation/cancel/<int:res_id>')
@admin_required
def cancel_reservation(res_id):
    try:
        db = get_db()
        res = db.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)).fetchone()
        
        if res:
            db.execute("UPDATE products SET stock = stock + 1 WHERE id = ?", (res['product_id'],))
            db.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (res_id,))
            db.commit()
            flash('تم إلغاء الحجز', 'info')
        
        return redirect(url_for('admin_reservations'))
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect(url_for('admin_reservations'))

@app.route('/admin/reservation/delete/<int:res_id>')
@admin_required
def delete_reservation(res_id):
    try:
        db = get_db()
        db.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
        db.commit()
        flash('🗑️ تم حذف الحجز نهائياً', 'success')
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
    return redirect(url_for('admin_reservations'))

# ==================== BLOCK CUSTOMERS ====================

@app.route('/admin/blocked')
@admin_required
def blocked_customers():
    try:
        db = get_db()
        blocked = db.execute("SELECT * FROM blocked_customers ORDER BY created_at DESC").fetchall()
        return render_template('admin/blocked.html', blocked=blocked, shop_name=SHOP_NAME)
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect('/admin/dashboard')

@app.route('/admin/block/add', methods=['POST'])
@admin_required
def add_blocked():
    try:
        db = get_db()
        phone = request.form.get('phone', '').strip()
        name = request.form.get('name', '').strip()
        reason = request.form.get('reason', '').strip()
        
        if not phone:
            flash('يرجى إدخال رقم الهاتف', 'error')
            return redirect(url_for('blocked_customers'))
        
        db.execute('''
            INSERT INTO blocked_customers (phone, name, reason, blocked_by)
            VALUES (?, ?, ?, ?)
        ''', (phone, name, reason, 'Admin'))
        db.commit()
        flash(f'⛔ تم حظر العميل {phone} بنجاح', 'success')
    except sqlite3.IntegrityError:
        flash('هذا الرقم محظور مسبقاً', 'warning')
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
    
    return redirect(url_for('blocked_customers'))

@app.route('/admin/block/remove/<int:block_id>')
@admin_required
def remove_blocked(block_id):
    try:
        db = get_db()
        blocked = db.execute("SELECT * FROM blocked_customers WHERE id = ?", (block_id,)).fetchone()
        if blocked:
            db.execute("DELETE FROM blocked_customers WHERE id = ?", (block_id,))
            db.commit()
            flash(f'✅ تم إلغاء حظر {blocked["phone"]}', 'success')
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
    return redirect(url_for('blocked_customers'))

# ==================== MAIN ====================
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
