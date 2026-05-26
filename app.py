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
ADMIN_PASSWORD = '78323'
RESERVATION_PHONE = '773852062'
MAINTENANCE_PHONE = '779505979'
PROGRAMMING_PHONE = '783234925'
APP_NAME = 'أرين'
SHOP_NAME = 'محل الراشد للجوالات'
SHOP_LOCATION = 'المهرة - الغيضة - الهنجر - سوق بن خودم'

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
                product_id INTEGER,
                customer_name TEXT,
                phone TEXT,
                status TEXT DEFAULT "pending",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                phone TEXT,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
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

# ========== دوال مساعدة ==========
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
    return session.get('admin_unlocked') == True

# ========== المسارات ==========
@app.route('/')
def index():
    return render_template('index.html', app_name=APP_NAME)

@app.route('/products')
def products():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    products_list = get_products(category, search)
    categories = ['شاشات', 'بطاريات', 'سماعات', 'كفرات', 'شواحن', 'هواتف']
    return render_template('products.html', 
                         products=products_list, 
                         categories=categories,
                         current_category=category,
                         search=search,
                         is_admin=is_admin(),
                         reservation_phone=RESERVATION_PHONE)

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', phone=MAINTENANCE_PHONE)

@app.route('/programming')
def programming():
    return render_template('programming.html', phone=PROGRAMMING_PHONE)

# ========== صفحة الموقع ==========
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
                background:radial-gradient(ellipse at center, #1a1a2e 0%, #000 100%);
                color:#fff;
                min-height:100vh;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                padding:20px;
                overflow:hidden;
            }
            .card {
                background:linear-gradient(145deg, rgba(212,175,55,0.05), rgba(255,255,255,0.02));
                border:1px solid rgba(212,175,55,0.2);
                border-radius:30px;
                padding:50px 35px;
                max-width:420px;
                width:100%;
                text-align:center;
                box-shadow:0 25px 80px rgba(212,175,55,0.1), inset 0 1px 0 rgba(255,255,255,0.05);
                animation: float 4s ease-in-out infinite;
                position:relative;
                overflow:hidden;
            }
            .card::before {
                content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%;
                background:radial-gradient(circle, rgba(212,175,55,0.1) 0%, transparent 70%);
                animation: rotate 15s linear infinite;
            }
            @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            @keyframes float {
                0%,100% { transform: translateY(0); }
                50% { transform: translateY(-15px); }
            }
            .pin {
                font-size:5rem;
                margin-bottom:20px;
                filter: drop-shadow(0 0 30px rgba(212,175,55,0.6));
                position:relative; z-index:1;
            }
            h1 {
                color:#d4af37;
                font-size:1.8rem;
                font-weight:900;
                margin-bottom:15px;
                text-shadow:0 0 20px rgba(212,175,55,0.3);
                position:relative; z-index:1;
            }
            .loc {
                color:#aaa;
                font-size:1.05rem;
                line-height:2;
                margin-bottom:30px;
                position:relative; z-index:1;
            }
            .loc strong { color:#d4af37; }
            .check {
                color:#2ecc71;
                font-weight:900;
                font-size:1.2rem;
                margin-top:10px;
                display:block;
                text-shadow:0 0 10px rgba(46,204,113,0.3);
            }
            .btn {
                display:block;
                width:100%;
                padding:16px;
                margin-bottom:15px;
                border-radius:18px;
                border:none;
                font-family:'Cairo',sans-serif;
                font-size:1.05rem;
                font-weight:700;
                cursor:pointer;
                text-decoration:none;
                transition:all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position:relative; z-index:1;
            }
            .btn-maps {
                background:linear-gradient(135deg, #d4af37, #b8941f);
                color:#000;
                box-shadow:0 8px 30px rgba(212,175,55,0.3);
            }
            .btn-maps:hover { transform:translateY(-3px) scale(1.02); box-shadow:0 15px 40px rgba(212,175,55,0.4); }
            .btn-back {
                background:rgba(255,255,255,0.03);
                color:#888;
                border:1px solid rgba(255,255,255,0.08);
                backdrop-filter:blur(10px);
            }
            .btn-back:hover { background:rgba(255,255,255,0.08); color:#fff; border-color:rgba(212,175,55,0.3); }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="pin">📍</div>
            <h1>""" + SHOP_NAME + """</h1>
            <div class="loc">
                <strong>📌 المهرة - الغيضة</strong><br>
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

# ========== إشعارات ==========
@app.route('/notify_me', methods=['POST'])
def notify_me():
    product_name = request.form.get('product_name')
    phone = request.form.get('phone', '')
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO alerts (product_name, phone) VALUES (?, ?)", (product_name, phone))
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
    c.execute("SELECT COUNT(*) as total FROM products")
    total_products = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM reservations WHERE status = 'pending'")
    pending_reservations = c.fetchone()['total']
    try:
        return render_template('admin/dashboard.html', total_products=total_products, pending_reservations=pending_reservations)
    except:
        return f"""
        <!DOCTYPE html>
        <html dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{ background:#000; color:#fff; font-family:'Cairo',sans-serif; padding:20px; }}
            .box {{ background:rgba(255,255,255,0.03); border:1px solid rgba(212,175,55,0.2); border-radius:25px; padding:35px; margin:20px 0; backdrop-filter:blur(20px); }}
            h1 {{ color:#d4af37; font-size:1.8rem; }}
            .stat {{ display:inline-block; background:linear-gradient(145deg, rgba(212,175,55,0.1), transparent); border:1px solid rgba(212,175,55,0.2); border-radius:20px; padding:25px; margin:10px; min-width:160px; text-align:center; transition:all 0.3s; }}
            .stat:hover {{ transform:translateY(-5px); box-shadow:0 10px 30px rgba(212,175,55,0.15); }}
            .num {{ font-size:2.5rem; color:#d4af37; font-weight:900; text-shadow:0 0 20px rgba(212,175,55,0.3); }}
            a {{ color:#d4af37; text-decoration:none; display:block; margin:15px 0; font-size:1.1rem; padding:15px; border-radius:15px; background:rgba(212,175,55,0.05); border:1px solid rgba(212,175,55,0.1); transition:all 0.3s; }}
            a:hover {{ background:rgba(212,175,55,0.15); transform:translateX(-5px); }}
        </style></head><body>
        <h1>👑 لوحة تحكم {APP_NAME}</h1>
        <div class="box">
            <div class="stat"><div class="num">{total_products}</div><div style="color:#aaa;">المنتجات</div></div>
            <div class="stat"><div class="num">{pending_reservations}</div><div style="color:#aaa;">حجوزات معلقة</div></div>
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
        SELECT r.*, p.name as product_name, p.price, p.currency
        FROM reservations r
        LEFT JOIN products p ON r.product_id = p.id
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
    c.execute("UPDATE reservations SET status = 'confirmed' WHERE id = ?", (reservation_id,))
    c.execute("UPDATE products SET stock = stock - 1 WHERE id = (SELECT product_id FROM reservations WHERE id = ?)", (reservation_id,))
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

# ========== API الحجز (بدون تسجيل دخول) ==========
@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    data = request.get_json() or request.form
    product_id = data.get('product_id')
    customer_name = data.get('customer_name', 'عميل')
    phone = data.get('phone', '')
    
    if not product_id:
        return jsonify({'success': False, 'error': 'معرف المنتج مطلوب'}), 400
    
    product = get_product(product_id)
    if not product:
        return jsonify({'success': False, 'error': 'المنتج غير موجود'}), 404
    
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO reservations (product_id, customer_name, phone, status) VALUES (?, ?, ?, ?)",
                 (product_id, customer_name, phone, 'pending'))
        db.commit()
        return jsonify({
            'success': True,
            'message': 'تم إنشاء الحجز بنجاح!',
            'reservation_id': c.lastrowid,
            'status': 'pending'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservation_whatsapp/<int:reservation_id>')
def reservation_whatsapp(reservation_id):
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT r.*, p.name as product_name, p.price, p.currency
        FROM reservations r
        LEFT JOIN products p ON r.product_id = p.id
        WHERE r.id = ?
    """, (reservation_id,))
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
