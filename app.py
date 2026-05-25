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
DATABASE = 'laqta.db'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
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
            'CREATE TABLE IF NOT EXISTS reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, customer_name TEXT, phone TEXT, status TEXT DEFAULT "pending", created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS user_devices (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, device_name TEXT, part_name TEXT, purchase_date TEXT, warranty_months INTEGER DEFAULT 6, last_notified TEXT)',
            'CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT, phone TEXT, notified INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE IF NOT EXISTS otp_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, code TEXT, expires_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
        ]
        for t in tables:
            conn.execute(t)
        conn.commit()

def migrate_db():
    with get_db() as conn:
        cols = [c[1] for c in conn.execute('PRAGMA table_info(products)').fetchall()]
        if 'currency' not in cols:
            conn.execute('ALTER TABLE products ADD COLUMN currency TEXT DEFAULT "ر.ي"')
            conn.commit()
        if 'original_price' not in cols:
            conn.execute('ALTER TABLE products ADD COLUMN original_price INTEGER DEFAULT 0')
            conn.commit()
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
                        notify(ref_by, 'إحالة ناجحة!', 'صديقك ' + name + ' سجل بكودك. ربحت 50 نقطة!')
                conn.execute('INSERT INTO users (name,phone,password,referral_code,referred_by) VALUES (?,?,?,?,?)', (name, phone, pwd, code, ref_by))
                conn.commit()
            flash('تم التسجيل! سجل دخولك', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', app_name=APP_NAME)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم الخروج', 'info')
    return redirect(url_for('index'))

@app.route('/products')
def products():
    cat = request.args.get('category','all')
    search = request.args.get('search','').strip()
    with get_db() as conn:
        q = 'SELECT * FROM products WHERE status="available"'
        p = []
        if cat != 'all':
            q += ' AND category=?'
            p.append(cat)
        if search:
            q += ' AND (name LIKE ? OR description LIKE ?)'
            p.append('%'+search+'%')
            p.append('%'+search+'%')
        q += ' AND stock>0 ORDER BY id DESC'
        prods = conn.execute(q, p).fetchall()
        cats = conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()
    pts, unread, is_adm, ures = 0, 0, False, {}
    notifs = []
    if 'user_id' in session:
        pts = get_points(session['user_id'])
        with get_db() as conn:
            unread = len(conn.execute('SELECT * FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchall())
            is_adm = session.get('is_admin', False)
            notifs = conn.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
            for r in conn.execute('SELECT product_id,status FROM reservations WHERE user_id=?', (session['user_id'],)).fetchall():
                ures[r['product_id']] = r['status']
    resp = make_response(render_template('products.html', products=prods, categories=cats, user_points=pts, unread_count=unread, is_admin=is_adm, user_reservations=ures, notifications=notifs, app_name=APP_NAME))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/reserve', methods=['POST'])
@login_required
def reserve():
    pid = request.form.get('product_id')
    with get_db() as conn:
        prod = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if not prod:
            flash('المنتج غير موجود', 'error')
            return redirect(url_for('products'))
        ex = conn.execute('SELECT id,status FROM reservations WHERE user_id=? AND product_id=?', (session['user_id'], pid)).fetchone()
        if ex:
            flash('لديك حجز على هذه القطعة بالفعل', 'warning')
            return redirect(url_for('products'))
        conn.execute('INSERT INTO reservations (user_id,product_id,customer_name,phone,status) VALUES (?,?,?,?,?)', (session['user_id'], pid, session.get('user_name',''), session.get('user_phone',''), 'pending'))
        conn.commit()
        msg = '*حجز جديد من أرين* 🔔\n\n*العميل:* ' + session.get('user_name','') + '\n*الهاتف:* ' + session.get('user_phone','') + '\n*القطعة:* ' + prod['name'] + '\n*السعر:* ' + '{:,}'.format(prod['price']) + ' ' + prod.get('currency','ر.ي') + '\n\nيرجى التواصل للتأكيد.'
        notify(session['user_id'], 'حجز معلق', 'طلبك على ' + prod['name'] + ' معلق. سيتم تأكيده قريباً.')
        flash('تم إرسال طلب الحجز', 'success')
        return redirect(wa_link(RESERVATION_PHONE, msg))

@app.route('/confirm/<int:rid>', methods=['POST'])
@admin_required
def confirm(rid):
    with get_db() as conn:
        res = conn.execute('SELECT * FROM reservations WHERE id=?', (rid,)).fetchone()
        if res:
            conn.execute('UPDATE reservations SET status="confirmed" WHERE id=?', (rid,))
            conn.execute('UPDATE products SET stock=stock-1 WHERE id=?', (res['product_id'],))
            pr = conn.execute('SELECT stock FROM products WHERE id=?', (res['product_id'],)).fetchone()
            if pr and pr['stock'] <= 0:
                conn.execute('UPDATE products SET status="reserved" WHERE id=?', (res['product_id'],))
            conn.commit()
            if res['user_id']:
                add_points(res['user_id'], 20)
                notify(res['user_id'], 'تم التأكيد!', 'تم تأكيد حجزك وربحت 20 نقطة!')
                u = conn.execute('SELECT phone,name FROM users WHERE id=?', (res['user_id'],)).fetchone()
                if u:
                    return redirect(wa_link(u['phone'], 'أهلاً ' + u['name'] + '! ✅\nتم تأكيد حجزك في أرين.\nربحت 20 نقطة ولاء.'))
            flash('تم التأكيد', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/cancel/<int:rid>', methods=['POST'])
@admin_required
def cancel(rid):
    with get_db() as conn:
        res = conn.execute('SELECT * FROM reservations WHERE id=?', (rid,)).fetchone()
        if res and res['user_id']:
            u = conn.execute('SELECT phone,name FROM users WHERE id=?', (res['user_id'],)).fetchone()
            if u:
                wa_link(u['phone'], 'عذراً ' + u['name'] + ' ❌\nتم إلغاء حجزك.')
            notify(res['user_id'], 'تم الإلغاء', 'تم إلغاء حجزك.')
        conn.execute('UPDATE reservations SET status="cancelled" WHERE id=?', (rid,))
        conn.commit()
        flash('تم الإلغاء', 'info')
    return redirect(url_for('admin_reservations'))

@app.route('/delete_reservation/<int:rid>', methods=['POST'])
@admin_required
def delete_reservation(rid):
    with get_db() as conn:
        conn.execute('DELETE FROM reservations WHERE id=?', (rid,))
        conn.commit()
    flash('تم حذف الحجز نهائياً', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/my_devices')
@login_required
def my_devices():
    with get_db() as conn:
        devs = conn.execute('SELECT * FROM user_devices WHERE user_id=? ORDER BY purchase_date DESC', (session['user_id'],)).fetchall()
        today = datetime.now().date()
        for d in devs:
            try:
                pd = datetime.strptime(d['purchase_date'], '%Y-%m-%d').date()
                we = pd + timedelta(days=d['warranty_months']*30)
                dl = (we - today).days
                if 0 < dl <= 15 and d['last_notified'] != str(today):
                    notify(session['user_id'], 'تنبيه الضمان', 'جهاز ' + d['device_name'] + ' (' + d['part_name'] + ') باقي ' + str(dl) + ' يوم على انتهاء الضمان. احجز فحصاً مجانياً!')
                    conn.execute('UPDATE user_devices SET last_notified=? WHERE id=?', (str(today), d['id']))
                    conn.commit()
            except: pass
    return render_template('my_devices.html', devices=devs, app_name=APP_NAME)

@app.route('/add_device', methods=['POST'])
@login_required
def add_device():
    with get_db() as conn:
        conn.execute('INSERT INTO user_devices (user_id,device_name,part_name,purchase_date,warranty_months) VALUES (?,?,?,?,?)',
            (session['user_id'], request.form.get('device_name'), request.form.get('part_name'), request.form.get('purchase_date'), request.form.get('warranty_months',6)))
        conn.commit()
    add_points(session['user_id'], 5)
    flash('تم إضافة الجهاز وربحت 5 نقاط!', 'success')
    return redirect(url_for('my_devices'))

@app.route('/delete_device/<int:did>', methods=['POST'])
@login_required
def delete_device(did):
    with get_db() as conn:
        conn.execute('DELETE FROM user_devices WHERE id=? AND user_id=?', (did, session['user_id']))
        conn.commit()
    flash('تم حذف الجهاز', 'success')
    return redirect(url_for('my_devices'))

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html', app_name=APP_NAME)

@app.route('/book_maintenance', methods=['POST'])
def book_maintenance():
    service = request.form.get('service','')
    name = request.form.get('name','') or session.get('user_name','')
    phone = request.form.get('phone','') or session.get('user_phone','')
    device = request.form.get('device','')
    msg = '*طلب صيانة من أرين* 🔧\n\n*العميل:* ' + name + '\n*الهاتف:* ' + phone + '\n*الخدمة:* ' + service + '\n*الجهاز:* ' + device + '\n\nيرجى التواصل للتنسيق.'
    flash('تم إرسال طلب الصيانة للمهندس راشد', 'success')
    return redirect(wa_link(MAINTENANCE_PHONE, msg))

@app.route('/programming')
def programming():
    return render_template('programming.html', app_name=APP_NAME)

@app.route('/book_programming', methods=['POST'])
def book_programming():
    service = request.form.get('service','')
    name = request.form.get('name','') or session.get('user_name','')
    phone = request.form.get('phone','') or session.get('user_phone','')
    device = request.form.get('device','')
    msg = '*طلب برمجة من أرين* 💻\n\n*العميل:* ' + name + '\n*الهاتف:* ' + phone + '\n*الخدمة:* ' + service + '\n*الجهاز:* ' + device + '\n\nيرجى التواصل للتنسيق.'
    flash('تم إرسال طلب البرمجة للمبرمج محمد', 'success')
    return redirect(wa_link(PROGRAMMING_PHONE, msg))

@app.route('/loyalty')
@login_required
def loyalty():
    pts = get_points(session['user_id'])
    rwds = [
        {'points':100,'reward':'صيانة مجانية','icon':'🔧'},
        {'points':200,'reward':'خصم 20%','icon':'🎁'},
        {'points':300,'reward':'كفر حماية','icon':'🛡️'},
        {'points':500,'reward':'سماعة بلوتوث','icon':'🎧'},
        {'points':800,'reward':'شاحن سريع','icon':'🔌'},
        {'points':1000,'reward':'شاشة مجانية','icon':'📱'}
    ]
    return render_template('loyalty.html', points=pts, rewards=rwds, app_name=APP_NAME)

@app.route('/notify_me', methods=['POST'])
def notify_me():
    with get_db() as conn:
        conn.execute('INSERT INTO alerts (user_id,product_name,phone) VALUES (?,?,?)',
            (session.get('user_id'), request.form.get('product_name'), request.form.get('phone')))
        conn.commit()
    flash('سنُعلمك فور التوفر! 🔔', 'success')
    return redirect(url_for('products'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html', app_name=APP_NAME)

@app.route('/admin/products', methods=['GET','POST'])
@admin_required
def admin_products():
    if request.method == 'POST':
        image_url = ''
        file = request.files.get('product_image') or request.files.get('product_image_upload')
        if file and allowed_file(file.filename):
            filename = 'prod_' + str(int(datetime.now().timestamp())) + '_' + file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = '/static/uploads/' + filename
        elif request.form.get('image_url'):
            image_url = request.form.get('image_url')
        
        with get_db() as conn:
            conn.execute('INSERT INTO products (name,price,original_price,image,description,category,stock,currency,is_rare) VALUES (?,?,?,?,?,?,?,?,?)',
                (request.form.get('name'), request.form.get('price'), request.form.get('original_price'), image_url,
                 request.form.get('description',''), request.form.get('category','general'), request.form.get('stock',1),
                 request.form.get('currency','ر.ي'), 1 if request.form.get('is_rare') else 0))
            conn.commit()
            nm = request.form.get('name')
            for u in conn.execute('SELECT id FROM users').fetchall():
                notify(u['id'], 'وصل جديد!', 'قطعة جديدة: ' + nm + ' متوفرة الآن!')
        flash('تمت الإضافة وإشعار العملاء', 'success')
    with get_db() as conn:
        prods = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    return render_template('admin/products.html', products=prods, app_name=APP_NAME)

@app.route('/delete_product/<int:pid>', methods=['POST'])
@admin_required
def delete_product(pid):
    with get_db() as conn:
        conn.execute('DELETE FROM products WHERE id=?', (pid,))
        conn.commit()
    flash('تم حذف المنتج نهائياً', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    with get_db() as conn:
        res = conn.execute('''SELECT r.*, p.name as product_name, p.price, p.currency, u.name as user_name, u.phone as user_phone
            FROM reservations r JOIN products p ON r.product_id=p.id LEFT JOIN users u ON r.user_id=u.id ORDER BY r.id DESC''').fetchall()
    return render_template('admin/reservations.html', reservations=res, app_name=APP_NAME)

@app.route('/claim_reward', methods=['POST'])
@login_required
def claim_reward():
    rp = int(request.form.get('points',0))
    rn = request.form.get('reward_name','')
    if get_points(session['user_id']) < rp:
        flash('نقاطك غير كافية', 'error')
        return redirect(url_for('loyalty'))
    with get_db() as conn:
        conn.execute('UPDATE users SET points=points-? WHERE id=?', (rp, session['user_id']))
        conn.commit()
    flash('تم استبدال النقاط!', 'success')
    return redirect(wa_link(session['user_phone'], 'مبروك! تم استبدال ' + str(rp) + ' نقطة بـ: ' + rn))

@app.route('/share/<int:pid>')
def share(pid):
    with get_db() as conn:
        p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    msg = '🔥 عرض من أرين!\n\n📱 ' + p['name'] + '\n💰 ' + '{:,}'.format(p['price']) + ' ' + p.get('currency','ر.ي') + '\n\nحمّل التطبيق!'
    return redirect(wa_link(RESERVATION_PHONE, msg))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
