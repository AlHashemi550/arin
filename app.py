import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'areen_secret_key_2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'laqta.db')

# ─── Helper: DB Connection ───
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

# ─── Initialize Tables (Keep existing data!) ───
def init_db():
    db = get_db()
    
    # Products
    db.execute('''
        CREATE TABLE IF NOT EXISTS products (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Reservations
    db.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
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
        )
    ''')
    
    # Services (Maintenance & Programming)
    db.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Users
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            banned INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Notifications
    db.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_phone TEXT,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.commit()

@app.before_request
def before_request():
    init_db()

# ─── Context Processor ───
@app.context_processor
def inject_globals():
    return {
        'now': datetime.now(),
        'admin_password': '78323'
    }

# ═══════════════════════════════════════════════════════
# PUBLIC ROUTES
# ═══════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/products')
def products():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    query = "SELECT * FROM products WHERE 1=1"
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
    return render_template('products.html', products=products_list, 
                           category=category, search=search)

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

# ─── API: Reserve Product ───
@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    data = request.get_json()
    product_id = data.get('product_id')
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    
    if not name or not phone:
        return jsonify({'success': False, 'message': 'الرجاء إدخال الاسم والرقم'})
    
    product = query_db("SELECT * FROM products WHERE id=?", [product_id], one=True)
    if not product:
        return jsonify({'success': False, 'message': 'المنتج غير موجود'})
    
    # Check if already reserved/confirmed
    existing = query_db("SELECT * FROM reservations WHERE product_id=? AND status IN ('pending','confirmed')", 
                        [product_id], one=True)
    if existing:
        return jsonify({'success': False, 'message': 'هذا المنتج محجوز بالفعل'})
    
    if product['quantity'] <= 0:
        return jsonify({'success': False, 'message': 'المنتج غير متوفر'})
    
    # Create reservation
    rid = execute_db('''
        INSERT INTO reservations (product_id, customer_name, customer_phone, status, service_type)
        VALUES (?, ?, ?, 'pending', 'product')
    ''', [product_id, name, phone])
    
    # Update product status to pending
    execute_db("UPDATE products SET status='pending' WHERE id=?", [product_id])
    
    # Add/update user
    user = query_db("SELECT * FROM users WHERE phone=?", [phone], one=True)
    if not user:
        execute_db("INSERT INTO users (name, phone) VALUES (?, ?)", [name, phone])
    
    # Build WhatsApp message
    msg = f"حجز جديد من تطبيق AREEN%n%nالمنتج: {product['name']}%nالسعر: {product['price']} {product['currency']}%n%nالعميل: {name}%nالرقم: {phone}%n%nيرجى التواصل للتأكيد."
    msg = msg.replace('%n', '%0A')
    whatsapp_url = f"https://wa.me/967773852062?text={msg}"
    
    return jsonify({
        'success': True,
        'reservation_id': rid,
        'whatsapp_url': whatsapp_url,
        'message': 'تم رفع الحجز بنجاح! جارِ تحويلك لواتساب...'
    })

# ─── API: Notify Me ───
@app.route('/api/notify-me', methods=['POST'])
def api_notify_me():
    data = request.get_json()
    product_id = data.get('product_id')
    phone = data.get('phone', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'message': 'الرجاء إدخال الرقم'})
    
    execute_db('''
        INSERT INTO notifications (user_phone, message, type)
        VALUES (?, ?, 'restock')
    ''', [phone, f"سيتم إشعارك عند توفر المنتج #{product_id}"])
    
    return jsonify({'success': True, 'message': 'سنخبرك فور توفر المنتج ✅'})

# ─── API: Service Request (Maintenance/Programming) ───
@app.route('/api/service-request', methods=['POST'])
def api_service_request():
    data = request.get_json()
    service_type = data.get('type')  # maintenance or programming
    service_id = data.get('service_id')
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    device = data.get('device', '').strip()
    
    if not name or not phone or not device:
        return jsonify({'success': False, 'message': 'الرجاء ملء جميع الحقول'})
    
    service = query_db("SELECT * FROM services WHERE id=?", [service_id], one=True)
    service_title = service['title'] if service else 'خدمة غير محددة'
    
    # Save to reservations as service
    execute_db('''
        INSERT INTO reservations (customer_name, customer_phone, device_model, service_type, status, notes)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', [name, phone, device, service_type, service_title])
    
    # Add/update user
    user = query_db("SELECT * FROM users WHERE phone=?", [phone], one=True)
    if not user:
        execute_db("INSERT INTO users (name, phone) VALUES (?, ?)", [name, phone])
    
    # WhatsApp
    if service_type == 'maintenance':
        target = "967779505979"
        engineer = "المهندس راشد اليافعي"
    else:
        target = "967783234925"
        engineer = "المبرمج محمد الهاشمي"
    
    msg = f"طلب {service_type} من تطبيق AREEN%n%nالخدمة: {service_title}%nالجهاز: {device}%n%nالعميل: {name}%nالرقم: {phone}%n%nيرجى التواصل."
    msg = msg.replace('%n', '%0A')
    whatsapp_url = f"https://wa.me/{target}?text={msg}"
    
    return jsonify({
        'success': True,
        'whatsapp_url': whatsapp_url,
        'message': f'جارِ تحويلك لواتساب {engineer}...'
    })


# ═══════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════

@app.route('/admin')
def admin_dashboard():
    if session.get('admin') != True:
        return redirect(url_for('admin_login'))
    
    stats = {
        'products': query_db("SELECT COUNT(*) as c FROM products", one=True)['c'],
        'reservations': query_db("SELECT COUNT(*) as c FROM reservations WHERE status='pending'", one=True)['c'],
        'confirmed': query_db("SELECT COUNT(*) as c FROM reservations WHERE status='confirmed'", one=True)['c'],
        'users': query_db("SELECT COUNT(*) as c FROM users", one=True)['c'],
        'banned': query_db("SELECT COUNT(*) as c FROM users WHERE banned=1", one=True)['c']
    }
    return render_template('admin/dashboard.html', stats=stats)

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
        
        execute_db('''
            INSERT INTO products (name, category, price, old_price, description, quantity, image, currency, rare, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available')
        ''', [name, category, price, old_price, description, quantity, image_data, currency, rare])
        
        # Notify all users
        users = query_db("SELECT phone FROM users")
        for u in users:
            execute_db('''
                INSERT INTO notifications (user_phone, message, type)
                VALUES (?, ?, 'new_product')
            ''', [u['phone'], f"🎉 منتج جديد: {name} متوفر الآن في AREEN!"])
        
        flash('تم إضافة المنتج بنجاح! 🔊', 'success')
        return redirect(url_for('admin_products'))
    
    products_list = query_db("SELECT * FROM products ORDER BY created_at DESC")
    return render_template('admin/products.html', products=products_list)

@app.route('/admin/product/delete/<int:pid>', methods=['POST'])
def admin_delete_product(pid):
    if session.get('admin') != True:
        return jsonify({'success': False})
    execute_db("DELETE FROM products WHERE id=?", [pid])
    # Also delete related pending reservations
    execute_db("DELETE FROM reservations WHERE product_id=? AND status='pending'", [pid])
    return jsonify({'success': True, 'message': 'تم الحذف نهائياً'})


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
    return render_template('admin/reservations.html', 
                           reservations=reservations_list, 
                           status_filter=status_filter)

@app.route('/admin/reservation/action', methods=['POST'])
def admin_reservation_action():
    if session.get('admin') != True:
        return jsonify({'success': False})
    
    data = request.get_json()
    rid = data.get('id')
    action = data.get('action')  # confirm, cancel, delete
    
    res = query_db("SELECT * FROM reservations WHERE id=?", [rid], one=True)
    if not res:
        return jsonify({'success': False, 'message': 'الحجز غير موجود'})
    
    if action == 'confirm':
        execute_db("UPDATE reservations SET status='confirmed', updated_at=CURRENT_TIMESTAMP WHERE id=?", [rid])
        if res['product_id']:
            execute_db("UPDATE products SET status='reserved', quantity=quantity-1 WHERE id=?", [res['product_id']])
        # Notify customer
        msg = "مبروك! ✅ تم تأكيد حجزك بنجاح. يمكنك التواصل معنا لاستلام طلبك."
        execute_db('''
            INSERT INTO notifications (user_phone, message, type)
            VALUES (?, ?, 'success')
        ''', [res['customer_phone'], msg])
        return jsonify({'success': True, 'message': 'تم التأكيد وإشعار العميل'})
    
    elif action == 'cancel':
        execute_db("UPDATE reservations SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?", [rid])
        if res['product_id']:
            execute_db("UPDATE products SET status='available' WHERE id=?", [res['product_id']])
        # Notify customer
        msg = "نأسف 🥲 تم إلغاء حجزك. يمكنك التواصل معنا للاستفسار."
        execute_db('''
            INSERT INTO notifications (user_phone, message, type)
            VALUES (?, ?, 'cancel')
        ''', [res['customer_phone'], msg])
        return jsonify({'success': True, 'message': 'تم الإلغاء وإشعار العميل'})
    
    elif action == 'delete':
        if res['product_id'] and res['status'] == 'pending':
            execute_db("UPDATE products SET status='available' WHERE id=?", [res['product_id']])
        execute_db("DELETE FROM reservations WHERE id=?", [rid])
        return jsonify({'success': True, 'message': 'تم الحذف'})
    
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
        execute_db('''
            INSERT INTO services (type, title, description, price, active)
            VALUES (?, ?, ?, ?, 1)
        ''', [stype, title, description, price])
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
    uid = data.get('id')
    coins = data.get('coins', 0)
    execute_db("UPDATE users SET coins=? WHERE id=?", [coins, uid])
    return jsonify({'success': True})

# ─── API: Check Notifications ───
@app.route('/api/notifications/<phone>')
def api_notifications(phone):
    notes = query_db("SELECT * FROM notifications WHERE user_phone=? AND is_read=0 ORDER BY created_at DESC", [phone])
    # Mark as read
    execute_db("UPDATE notifications SET is_read=1 WHERE user_phone=?", [phone])
    return jsonify({'notifications': [dict(n) for n in notes]})

# ─── Run ───
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
