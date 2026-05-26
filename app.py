import os
import sqlite3
import json
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'areen_secret_key_2026'

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'laqta.db')

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

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value)
    except:
        return []

def init_db():
    db = get_db()
    tables = [
        '''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            old_price REAL,
            description TEXT,
            quantity INTEGER DEFAULT 0,
            image TEXT,
            currency TEXT DEFAULT 'ر.ي',
            status TEXT DEFAULT 'available',
            rare INTEGER DEFAULT 0,
            seo_title TEXT,
            seo_desc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            total REAL NOT NULL,
            discount REAL DEFAULT 0,
            coupon_code TEXT,
            payment_method TEXT DEFAULT 'cod',
            status TEXT DEFAULT 'pending',
            items TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_name TEXT,
            user_phone TEXT,
            rating INTEGER DEFAULT 5,
            comment TEXT,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_percent INTEGER DEFAULT 10,
            active INTEGER DEFAULT 1,
            usage_limit INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            device_model TEXT,
            service_type TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            banned INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_phone TEXT,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    ]
    for table in tables:
        db.execute(table)
    
    # Default coupon
    db.execute("INSERT OR IGNORE INTO coupons (code, discount_percent, active, usage_limit) VALUES ('ARIN10', 10, 1, 100)")
    db.commit()

@app.before_request
def before_request():
    init_db()
    if 'cart_id' not in session:
        session['cart_id'] = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

@app.context_processor
def inject_globals():
    cart_count = 0
    if 'cart_id' in session:
        row = query_db("SELECT COALESCE(SUM(qty),0) as c FROM cart WHERE session_id=?", [session['cart_id']], one=True)
        cart_count = row['c'] if row else 0
    return {'now': datetime.now(), 'admin_password': '78323', 'cart_count': cart_count}

# ========== PUBLIC ROUTES ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/products')
def products():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    query = "SELECT * FROM products WHERE status!='deleted'"
    args = []
    if category != 'all':
        query += " AND category = ?"
        args.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        args.append(f'%{search}%')
        args.append(f'%{search}%')
    query += " ORDER BY created_at DESC"
    products_list = query_db(query, args)
    return render_template('products.html', products=products_list, category=category, search=search)

@app.route('/product/<int:pid>')
def product_detail(pid):
    product = query_db("SELECT * FROM products WHERE id=?", [pid], one=True)
    if not product:
        flash('المنتج غير موجود', 'danger')
        return redirect(url_for('products'))
    reviews = query_db("SELECT * FROM reviews WHERE product_id=? ORDER BY created_at DESC", [pid])
    avg = query_db("SELECT AVG(rating) as avg FROM reviews WHERE product_id=?", [pid], one=True)
    avg_rating = round(avg['avg'], 1) if avg and avg['avg'] else 0
    return render_template('product_detail.html', product=product, reviews=reviews, avg_rating=avg_rating)

@app.route('/cart')
def cart():
    cart_items = query_db('''
        SELECT c.*, p.name, p.price, p.old_price, p.image, p.currency, p.status, p.quantity as stock
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.session_id = ?
    ''', [session.get('cart_id', '')])
    total = sum(item['price'] * item['qty'] for item in cart_items)
    coupon_discount = session.get('coupon_discount', 0)
    final_total = total * (1 - coupon_discount/100)
    return render_template('cart.html', items=cart_items, total=total, discount=coupon_discount, final_total=final_total)

@app.route('/maintenance')
def maintenance():
    services = query_db("SELECT * FROM services WHERE type='maintenance' AND active=1")
    return render_template('maintenance.html', services=services)

@app.route('/programming')
def programming():
    services = query_db("SELECT * FROM services WHERE type='programming' AND active=1")
    return render_template('programming.html', services=services)

@app.route('/location')
def location():
    return render_template('location.html')

# ========== API ROUTES ==========

@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.get_json()
    product_id = data.get('product_id')
    qty = int(data.get('qty', 1))
    product = query_db("SELECT * FROM products WHERE id=? AND status='available'", [product_id], one=True)
    if not product:
        return jsonify({'success': False, 'message': 'المنتج غير متوفر'})
    if product['quantity'] < qty:
        return jsonify({'success': False, 'message': 'الكمية غير كافية'})
    existing = query_db("SELECT * FROM cart WHERE session_id=? AND product_id=?", [session['cart_id'], product_id], one=True)
    if existing:
        new_qty = existing['qty'] + qty
        if new_qty > product['quantity']:
            return jsonify({'success': False, 'message': 'الكمية المطلوبة غير متوفرة'})
        execute_db("UPDATE cart SET qty=? WHERE id=?", [new_qty, existing['id']])
    else:
        execute_db("INSERT INTO cart (session_id, product_id, qty) VALUES (?,?,?)", [session['cart_id'], product_id, qty])
    row = query_db("SELECT COALESCE(SUM(qty),0) as c FROM cart WHERE session_id=?", [session['cart_id']], one=True)
    return jsonify({'success': True, 'cart_count': row['c'] if row else 0, 'message': 'تمت الإضافة للعربة ✅'})

@app.route('/api/cart/update', methods=['POST'])
def api_cart_update():
    data = request.get_json()
    cart_id = data.get('cart_id')
    qty = int(data.get('qty', 1))
    if qty < 1:
        execute_db("DELETE FROM cart WHERE id=?", [cart_id])
    else:
        execute_db("UPDATE cart SET qty=? WHERE id=?", [qty, cart_id])
    return jsonify({'success': True})

@app.route('/api/cart/remove', methods=['POST'])
def api_cart_remove():
    data = request.get_json()
    execute_db("DELETE FROM cart WHERE id=?", [data.get('cart_id')])
    return jsonify({'success': True})

@app.route('/api/coupon/apply', methods=['POST'])
def api_coupon_apply():
    code = request.get_json().get('code', '').upper().strip()
    coupon = query_db("SELECT * FROM coupons WHERE code=? AND active=1", [code], one=True)
    if not coupon:
        session.pop('coupon_discount', None)
        session.pop('coupon_code', None)
        return jsonify({'success': False, 'message': 'كود الخصم غير صحيح'})
    if coupon['used_count'] >= coupon['usage_limit']:
        return jsonify({'success': False, 'message': 'انتهت صلاحية الكود'})
    session['coupon_discount'] = coupon['discount_percent']
    session['coupon_code'] = code
    return jsonify({'success': True, 'discount': coupon['discount_percent'], 'message': f'تم تطبيق خصم {coupon["discount_percent"]}% ✅'})

@app.route('/api/order/checkout', methods=['POST'])
def api_order_checkout():
    data = request.get_json()
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    payment = data.get('payment', 'cod')
    if not name or not phone:
        return jsonify({'success': False, 'message': 'الرجاء إدخال الاسم والرقم'})
    cart_items = query_db('''SELECT c.*, p.name, p.price, p.currency FROM cart c JOIN products p ON c.product_id = p.id WHERE c.session_id = ?''', [session.get('cart_id', '')])
    if not cart_items:
        return jsonify({'success': False, 'message': 'العربة فارغة'})
    total = sum(item['price'] * item['qty'] for item in cart_items)
    discount = session.get('coupon_discount', 0)
    final_total = total * (1 - discount/100)
    items_json = json.dumps([{'id': i['product_id'], 'name': i['name'], 'price': i['price'], 'qty': i['qty'], 'currency': i['currency']} for i in cart_items])
    order_id = execute_db('''INSERT INTO orders (customer_name, customer_phone, total, discount, coupon_code, payment_method, items) VALUES (?, ?, ?, ?, ?, ?, ?)''', [name, phone, final_total, discount, session.get('coupon_code'), payment, items_json])
    if session.get('coupon_code'):
        execute_db("UPDATE coupons SET used_count=used_count+1 WHERE code=?", [session['coupon_code']])
    lines = [f"🛒 طلب جديد من تطبيق AREEN", "", f"👤 العميل: {name}", f"📱 الرقم: {phone}", ""]
    for i, item in enumerate(cart_items, 1):
        lines.append(f"{i}. {item['name']} x{item['qty']} = {item['price']*item['qty']} {item['currency']}")
    lines.append("")
    lines.append(f"💰 المجموع: {total}")
    if discount > 0:
        lines.append(f"🎟️ خصم: {discount}%")
    lines.append(f"💵 النهائي: {round(final_total, 2)}")
    lines.append(f"💳 الدفع: {'عند الاستلام' if payment=='cod' else 'تحويل بنكي' if payment=='bank' else 'إلكتروني'}")
    lines.append("")
    lines.append("يرجى التواصل للتأكيد.")
    msg = '%0A'.join(lines)
    whatsapp_url = f"https://wa.me/967773852062?text={msg}"
    execute_db("DELETE FROM cart WHERE session_id=?", [session['cart_id']])
    session.pop('coupon_discount', None)
    session.pop('coupon_code', None)
    user = query_db("SELECT * FROM users WHERE phone=?", [phone], one=True)
    if not user:
        execute_db("INSERT INTO users (name, phone) VALUES (?, ?)", [name, phone])
    return jsonify({'success': True, 'order_id': order_id, 'whatsapp_url': whatsapp_url, 'message': 'تم إرسال الطلب! جارِ تحويلك لواتساب...'})

@app.route('/api/review', methods=['POST'])
def api_review():
    data = request.get_json()
    execute_db('''INSERT INTO reviews (product_id, user_name, user_phone, rating, comment) VALUES (?, ?, ?, ?, ?)''', [data.get('product_id'), data.get('name'), data.get('phone'), data.get('rating', 5), data.get('comment')])
    return jsonify({'success': True, 'message': 'شكراً لتقييمك! ⭐'})

@app.route('/api/share/product/<int:pid>')
def api_share_product(pid):
    product = query_db("SELECT * FROM products WHERE id=?", [pid], one=True)
    if not product:
        return jsonify({'success': False})
    msg = f"🛍️ منتج من AREEN%0A%0A{product['name']}%0A💰 {product['price']} {product['currency']}%0A%0Aشوف التفاصيل:"
    return jsonify({'success': True, 'whatsapp_url': f"https://wa.me/?text={msg}%0A{request.host_url}product/{pid}", 'facebook_url': f"https://www.facebook.com/sharer/sharer.php?u={request.host_url}product/{pid}"})

@app.route('/api/notify-me', methods=['POST'])
def api_notify_me():
    data = request.get_json()
    execute_db('''INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, 'restock')''', [data.get('phone', '').strip(), f"سيتم إشعارك عند توفر المنتج #{data.get('product_id')}"])
    return jsonify({'success': True, 'message': 'سنخبرك فور توفر المنتج ✅'})

@app.route('/api/service-request', methods=['POST'])
def api_service_request():
    data = request.get_json()
    service_type = data.get('type')
    service_id = data.get('service_id')
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    device = data.get('device', '').strip()
    if not name or not phone or not device:
        return jsonify({'success': False, 'message': 'الرجاء ملء جميع الحقول'})
    service = query_db("SELECT * FROM services WHERE id=?", [service_id], one=True)
    service_title = service['title'] if service else 'خدمة غير محددة'
    execute_db('''INSERT INTO reservations (customer_name, customer_phone, device_model, service_type, status, notes) VALUES (?, ?, ?, ?, 'pending', ?)''', [name, phone, device, service_type, service_title])
    user = query_db("SELECT * FROM users WHERE phone=?", [phone], one=True)
    if not user:
        execute_db("INSERT INTO users (name, phone) VALUES (?, ?)", [name, phone])
    target = "967779505979" if service_type == 'maintenance' else "967783234925"
    engineer = "المهندس راشد اليافعي" if service_type == 'maintenance' else "المبرمج محمد الهاشمي"
    msg = f"طلب {service_type} من تطبيق AREEN%0A%0Aالخدمة: {service_title}%0Aالجهاز: {device}%0A%0Aالعميل: {name}%0Aالرقم: {phone}%0A%0Aيرجى التواصل."
    whatsapp_url = f"https://wa.me/{target}?text={msg}"
    return jsonify({'success': True, 'whatsapp_url': whatsapp_url, 'message': f'جارِ تحويلك لواتساب {engineer}...'})

@app.route('/api/notifications/<phone>')
def api_notifications(phone):
    notes = query_db("SELECT * FROM notifications WHERE user_phone=? AND is_read=0 ORDER BY created_at DESC", [phone])
    execute_db("UPDATE notifications SET is_read=1 WHERE user_phone=?", [phone])
    return jsonify({'notifications': [dict(n) for n in notes]})

# ========== ADMIN ROUTES ==========

@app.route('/admin')
def admin_dashboard():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    stats = {
        'products': query_db("SELECT COUNT(*) as c FROM products WHERE status!='deleted'", one=True)['c'],
        'orders': query_db("SELECT COUNT(*) as c FROM orders WHERE status='pending'", one=True)['c'],
        'reservations': query_db("SELECT COUNT(*) as c FROM reservations WHERE status='pending'", one=True)['c'],
        'confirmed': query_db("SELECT COUNT(*) as c FROM reservations WHERE status='confirmed'", one=True)['c'],
        'users': query_db("SELECT COUNT(*) as c FROM users", one=True)['c'],
        'banned': query_db("SELECT COUNT(*) as c FROM users WHERE banned=1", one=True)['c'],
        'reviews': query_db("SELECT COUNT(*) as c FROM reviews", one=True)['c'],
        'coupons': query_db("SELECT COUNT(*) as c FROM coupons WHERE active=1", one=True)['c']
    }
    recent_orders = query_db("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5")
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '78323':
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('كلمة السر خاطئة', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('products'))

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = request.form.get('price', 0)
        old_price = request.form.get('old_price') or None
        description = request.form.get('description', '')
        quantity = request.form.get('quantity', 0)
        currency = request.form.get('currency', 'ر.ي')
        rare = 1 if request.form.get('rare') else 0
        image_data = request.form.get('image_data', '')
        seo_title = request.form.get('seo_title', name)
        seo_desc = request.form.get('seo_desc', description[:160] if description else name)
        execute_db('''INSERT INTO products (name, category, price, old_price, description, quantity, image, currency, rare, status, seo_title, seo_desc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)''', [name, category, price, old_price, description, quantity, image_data, currency, rare, seo_title, seo_desc])
        users = query_db("SELECT phone FROM users")
        for u in users:
            execute_db('''INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, 'new_product')''', [u['phone'], f"🎉 منتج جديد: {name} متوفر الآن في AREEN!"])
        flash('تم إضافة المنتج بنجاح! 🔊', 'success')
        return redirect(url_for('admin_products'))
    products_list = query_db("SELECT * FROM products WHERE status!='deleted' ORDER BY created_at DESC")
    return render_template('admin/products.html', products=products_list)

@app.route('/admin/product/delete/<int:pid>', methods=['POST'])
def admin_delete_product(pid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    execute_db("UPDATE products SET status='deleted' WHERE id=?", [pid])
    execute_db("DELETE FROM cart WHERE product_id=?", [pid])
    return jsonify({'success': True, 'message': 'تم الحذف'})

@app.route('/admin/orders')
def admin_orders():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    orders_list = query_db("SELECT * FROM orders ORDER BY created_at DESC")
    return render_template('admin/orders.html', orders=orders_list)

@app.route('/admin/order/action', methods=['POST'])
def admin_order_action():
    if session.get('admin') != True:
        return jsonify({'success': False})
    data = request.get_json()
    oid = data.get('id')
    action = data.get('action')
    order = query_db("SELECT * FROM orders WHERE id=?", [oid], one=True)
    if not order:
        return jsonify({'success': False})
    if action == 'confirm':
        execute_db("UPDATE orders SET status='confirmed' WHERE id=?", [oid])
        msg = f"مبروك! ✅ تم تأكيد طلبك #{oid}. يمكنك استلامه الآن."
        execute_db('INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, ?)', [order['customer_phone'], msg, 'success'])
    elif action == 'cancel':
        execute_db("UPDATE orders SET status='cancelled' WHERE id=?", [oid])
        msg = f"نأسف 🥲 تم إلغاء طلبك #{oid}. يمكنك التواصل معنا للاستفسار."
        execute_db('INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, ?)', [order['customer_phone'], msg, 'cancel'])
    elif action == 'delete':
        execute_db("DELETE FROM orders WHERE id=?", [oid])
    return jsonify({'success': True})

@app.route('/admin/coupons', methods=['GET', 'POST'])
def admin_coupons():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        code = request.form.get('code', '').upper().strip()
        discount = request.form.get('discount', 10)
        limit = request.form.get('limit', 100)
        execute_db('INSERT OR REPLACE INTO coupons (code, discount_percent, active, usage_limit) VALUES (?, ?, 1, ?)', [code, discount, limit])
        flash('تم إضافة الكوبون', 'success')
        return redirect(url_for('admin_coupons'))
    coupons_list = query_db("SELECT * FROM coupons ORDER BY created_at DESC")
    return render_template('admin/coupons.html', coupons=coupons_list)

@app.route('/admin/reservations')
def admin_reservations():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    status_filter = request.args.get('status', 'all')
    query = "SELECT r.*, p.name as product_name, p.price, p.currency FROM reservations r LEFT JOIN products p ON r.product_id = p.id WHERE 1=1"
    args = []
    if status_filter != 'all':
        query += " AND r.status = ?"
        args.append(status_filter)
    query += " ORDER BY r.created_at DESC"
    reservations_list = query_db(query, args)
    return render_template('admin/reservations.html', reservations=reservations_list, status_filter=status_filter)

@app.route('/admin/reservation/action', methods=['POST'])
def admin_reservation_action():
    if session.get('admin') != True:
        return jsonify({'success': False})
    data = request.get_json()
    rid = data.get('id')
    action = data.get('action')
    res = query_db("SELECT * FROM reservations WHERE id=?", [rid], one=True)
    if not res:
        return jsonify({'success': False, 'message': 'الحجز غير موجود'})
    if action == 'confirm':
        execute_db("UPDATE reservations SET status='confirmed', updated_at=CURRENT_TIMESTAMP WHERE id=?", [rid])
        if res['product_id']:
            execute_db("UPDATE products SET status='reserved', quantity=quantity-1 WHERE id=?", [res['product_id']])
        msg = "مبروك! ✅ تم تأكيد حجزك بنجاح. يمكنك التواصل معنا لاستلام طلبك."
        execute_db('INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, ?)', [res['customer_phone'], msg, 'success'])
        return jsonify({'success': True, 'message': 'تم التأكيد وإشعار العميل'})
    elif action == 'cancel':
        execute_db("UPDATE reservations SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?", [rid])
        if res['product_id']:
            execute_db("UPDATE products SET status='available' WHERE id=?", [res['product_id']])
        msg = "نأسف 🥲 تم إلغاء حجزك. يمكنك التواصل معنا للاستفسار."
        execute_db('INSERT INTO notifications (user_phone, message, type) VALUES (?, ?, ?)', [res['customer_phone'], msg, 'cancel'])
        return jsonify({'success': True, 'message': 'تم الإلغاء وإشعار العميل'})
    elif action == 'delete':
        if res['product_id'] and res['status'] == 'pending':
            execute_db("UPDATE products SET status='available' WHERE id=?", [res['product_id']])
        execute_db("DELETE FROM reservations WHERE id=?", [rid])
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/admin/services', methods=['GET', 'POST'])
def admin_services():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        stype = request.form.get('type')
        title = request.form.get('title')
        description = request.form.get('description', '')
        price = request.form.get('price', '')
        execute_db('INSERT INTO services (type, title, description, price, active) VALUES (?, ?, ?, ?, 1)', [stype, title, description, price])
        flash('تم إضافة الخدمة بنجاح', 'success')
        return redirect(url_for('admin_services'))
    maintenance = query_db("SELECT * FROM services WHERE type='maintenance' ORDER BY id DESC")
    programming = query_db("SELECT * FROM services WHERE type='programming' ORDER BY id DESC")
    return render_template('admin/services.html', maintenance=maintenance, programming=programming)

@app.route('/admin/service/toggle/<int:sid>', methods=['POST'])
def admin_toggle_service(sid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    svc = query_db("SELECT * FROM services WHERE id=?", [sid], one=True)
    if svc:
        new_active = 0 if svc['active'] else 1
        execute_db("UPDATE services SET active=? WHERE id=?", [new_active, sid])
    return jsonify({'success': True})

@app.route('/admin/service/delete/<int:sid>', methods=['POST'])
def admin_delete_service(sid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    execute_db("DELETE FROM services WHERE id=?", [sid])
    return jsonify({'success': True})

@app.route('/admin/users')
def admin_users():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    users_list = query_db("SELECT * FROM users ORDER BY created_at DESC")
    return render_template('admin/users.html', users=users_list)

@app.route('/admin/user/ban/<int:uid>', methods=['POST'])
def admin_ban_user(uid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    execute_db("UPDATE users SET banned=1 WHERE id=?", [uid])
    return jsonify({'success': True})

@app.route('/admin/user/unban/<int:uid>', methods=['POST'])
def admin_unban_user(uid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    execute_db("UPDATE users SET banned=0 WHERE id=?", [uid])
    return jsonify({'success': True})

@app.route('/admin/user/coins', methods=['POST'])
def admin_user_coins():
    if session.get('admin') != True:
        return jsonify({'success': False})
    data = request.get_json()
    execute_db("UPDATE users SET coins=? WHERE id=?", [data.get('coins', 0), data.get('id')])
    return jsonify({'success': True})

# ========== RUN ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
