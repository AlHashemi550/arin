import sqlite3
import random
import os
import urllib.parse
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'areen-secret-key-2026')
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
                service_type TEXT DEFAULT 'product',
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
                phone TEXT,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                name TEXT,
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
    tb = traceback.format_exc()
    return f"""
    <!DOCTYPE html>
    <html dir="rtl"><head><meta charset="UTF-8"><title>خطأ</title>
    <style>
        body {{ background:#000; color:#e74c3c; font-family:Cairo,sans-serif; padding:20px; }}
        .box {{ background:#111; border:1px solid #e74c3c; border-radius:15px; padding:20px; margin:20px 0; }}
        pre {{ color:#888; font-size:0.75rem; overflow-x:auto; white-space:pre-wrap; }}
        h2 {{ color:#d4af37; }}
        a {{ color:#d4af37; }}
    </style></head><body>
    <h2>⚠️ خطأ في السيرفر</h2>
    <div class="box">
        <p><strong>النوع:</strong> {type(error).__name__}</p>
        <p><strong>الرسالة:</strong> {str(error)}</p>
        <hr style="border-color:#333;">
        <pre>{tb}</pre>
    </div>
    <a href="/">🏠 العودة للرئيسية</a>
    </body></html>
    """, 500

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('index'))

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

def save_customer(phone, name=''):
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?, ?)", (phone, name))
        db.commit()
    except:
        pass

def notify_all_customers(title, message):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT DISTINCT phone FROM customers")
    customers = c.fetchall()
    for customer in customers:
        c.execute("INSERT INTO notifications (phone, title, message) VALUES (?, ?, ?)",
                 (customer['phone'], title, message))
    db.commit()

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
                         shop_name=SHOP_NAME,
                         reservation_phone=RESERVATION_PHONE)

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', phone=MAINTENANCE_PHONE)

@app.route('/programming')
def programming():
    return render_template('programming.html', phone=PROGRAMMING_PHONE)

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
    save_customer(phone)
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
    c.execute("SELECT COUNT(*) as total FROM reservations WHERE status = 'confirmed'")
    confirmed_reservations = c.fetchone()['total']
    try:
        return render_template('admin/dashboard.html', 
                             total_products=total_products, 
                             pending_reservations=pending_reservations,
                             confirmed_reservations=confirmed_reservations)
    except:
        return f"""
        <!DOCTYPE html>
        <html dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{ background:#000; color:#fff; font-family:'Cairo',sans-serif; padding:20px; }}
            .box {{ background:rgba(255,255,255,0.03); border:1px solid rgba(212,175,55,0.2); border-radius:25px; padding:35px; margin:20px 0; backdrop-filter:blur(20px); }}
            h1 {{ color:#d4af37; font-size:1.8rem; }}
            .stat {{ display:inline-block; background:linear-gradient(145deg, rgba(212,175,55,0.1), transparent); border:1px solid rgba(212,175,55,0.2); border-radius:20px; padding:25px; margin:10px; min-width:140px; text-align:center; transition:all 0.3s; }}
            .stat:hover {{ transform:translateY(-5px); box-shadow:0 10px 30px rgba(212,175,55,0.15); }}
            .num {{ font-size:2.2rem; color:#d4af37; font-weight:900; text-shadow:0 0 20px rgba(212,175,55,0.3); }}
            a {{ color:#d4af37; text-decoration:none; display:block; margin:15px 0; font-size:1.1rem; padding:15px; border-radius:15px; background:rgba(212,175,55,0.05); border:1px solid rgba(212,175,55,0.1); transition:all 0.3s; }}
            a:hover {{ background:rgba(212,175,55,0.15); transform:translateX(-5px); }}
        </style></head><body>
        <h1>👑 لوحة تحكم {APP_NAME}</h1>
        <div class="box">
            <div class="stat"><div class="num">{total_products}</div><div style="color:#aaa;">المنتجات</div></div>
            <div class="stat"><div class="num">{pending_reservations}</div><div style="color:#aaa;">معلقة</div></div>
            <div class="stat"><div class="num">{confirmed_reservations}</div><div style="color:#aaa;">مؤكدة</div></div>
        </div>
        <div class="box">
            <a href="/admin/products">📦 إدارة المنتجات</a>
            <a href="/admin/reservations">📋 إدارة الحجوزات</a>
            <a href="/admin/services">🔧 إدارة الخدمات</a>
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
        # تنبيه جميع العملاء
        notify_all_customers('🆕 منتج جديد!', f'تم إضافة {name} إلى متجر أرين. تفضل بزيارتنا!')
        flash('تم إضافة المنتج بنجاح وتم إشعار العملاء', 'success')
        return redirect(url_for('admin_products'))
    c.execute("SELECT * FROM products ORDER BY created_at DESC")
    products_list = c.fetchall()
    try:
        return render_template('admin/products.html', products=products_list)
    except:
        return redirect(url_for('admin_dashboard'))

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
    try:
        return render_template('admin/reservations.html', reservations=reservations)
    except:
        return redirect(url_for('admin_dashboard'))

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

# ========== API الحجز ==========
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
    
    save_customer(phone, customer_name)
    
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO reservations (product_id, customer_name, phone, service_type, status) VALUES (?, ?, ?, ?, ?)",
                 (product_id, customer_name, phone, 'product', 'pending'))
        db.commit()
        return jsonify({
            'success': True,
            'message': 'تم إنشاء الحجز بنجاح!',
            'reservation_id': c.lastrowid,
            'status': 'pending'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API الخدمات (صيانة/برمجة) ==========
@app.route('/api/service', methods=['POST'])
def api_service():
    data = request.get_json() or request.form
    service_type = data.get('service_type')  # 'maintenance' or 'programming'
    service_name = data.get('service_name')
    customer_name = data.get('customer_name', 'عميل')
    phone = data.get('phone', '')
    device = data.get('device', '')
    
    if not service_type or not service_name:
        return jsonify({'success': False, 'error': 'نوع الخدمة مطلوب'}), 400
    
    save_customer(phone, customer_name)
    
    # تحويل مباشر لواتساب
    if service_type == 'maintenance':
        target_phone = MAINTENANCE_PHONE
        target_name = 'المهندس راشد اليافعي'
    else:
        target_phone = PROGRAMMING_PHONE
        target_name = 'المبرمج محمد الهاشمي'
    
    message = f"""مرحباً {target_name}،
أرغب في خدمة الصيانة التالية:
🔧 الخدمة: {service_name}
📱 الجهاز: {device}
👤 الاسم: {customer_name}
📞 الرقم: {phone}
"""
    
    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/967{target_phone}?text={encoded_msg}"
    
    return jsonify({
        'success': True,
        'message': f'جاري التحويل لواتساب {target_name}',
        'whatsapp_url': whatsapp_url
    })

# ========== API إشعار الصوتي ==========
@app.route('/api/notifications')
def get_notifications():
    phone = request.args.get('phone', '')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM notifications WHERE phone = ? AND is_read = 0 ORDER BY created_at DESC", (phone,))
    notifications = c.fetchall()
    # تحديث كمقروء
    c.execute("UPDATE notifications SET is_read = 1 WHERE phone = ?", (phone,))
    db.commit()
    return jsonify({
        'success': True,
        'count': len(notifications),
        'notifications': [{'title': n['title'], 'message': n['message']} for n in notifications]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
