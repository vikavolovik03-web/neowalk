from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from models import User, Product, Brand, Category, CartItem, Order, OrderItem
from extensions import db, login_manager
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import os

app = Flask(__name__)  # ИСПРАВЛЕНО: __name__ вместо name
app.config['SECRET_KEY'] = 'neowalk-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///neowalk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Декоратор для проверки админа
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен. Только для администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    products = Product.query.filter(Product.stock > 0).limit(8).all()
    new_products = Product.query.filter(Product.stock > 0).order_by(Product.id.desc()).limit(4).all()
    sale_products = Product.query.filter(Product.old_price.isnot(None), Product.stock > 0).limit(2).all()
    return render_template('index.html', products=products, new_products=new_products, sale_products=sale_products)

@app.route('/catalog')
def catalog():
    brands = ['Nike', 'Adidas', 'Asics', 'Balenciaga', 'Puma', 'New Balance']
    products = Product.query.filter(Product.stock > 0).all()
    return render_template('catalog.html', products=products, brands=brands)

@app.route('/catalog/<brand_name>')
def catalog_brand(brand_name):
    brand_map = {'nike': 'Nike', 'adidas': 'Adidas', 'asics': 'Asics', 'balenciaga': 'Balenciaga', 'puma': 'Puma'}
    brand_title = brand_map.get(brand_name.lower(), brand_name)
    products = Product.query.join(Brand).filter(Brand.name == brand_title, Product.stock > 0).all()
    return render_template('catalog.html', products=products, brands=list(brand_map.values()), current_brand=brand_title)

@app.route('/product/<int:product_id>')  # ИСПРАВЛЕНО: правильный синтаксис
def product(product_id):
    prod = Product.query.get_or_404(product_id)
    related = Product.query.join(Brand).filter(
        Brand.name == prod.brand.name,
        Product.id != prod.id,
        Product.stock > 0
    ).limit(4).all()
    return render_template('product.html', product=prod, related_products=related)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])  # ИСПРАВЛЕНО
def add_to_cart(product_id):
    if not current_user.is_authenticated:
        flash('❌ Войдите, чтобы добавить товар', 'error')
        return redirect(url_for('login'))
    
    qty = int(request.form.get('quantity', 1))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if item:
        item.quantity += qty
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=qty))
    
    db.session.commit()
    flash('✓ Добавлено в корзину', 'success')
    return redirect(url_for('cart'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    product_id = request.form.get('product_id')
    action = request.form.get('action')
    
    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=int(product_id)).first()
        if item:
            if action == 'increase':
                item.quantity += 1
            elif action == 'decrease':
                item.quantity -= 1
                if item.quantity <= 0:
                    db.session.delete(item)
            db.session.commit()
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])  # ИСПРАВЛЕНО
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            flash('✓ Товар удалён', 'success')
    return redirect(url_for('cart'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        login_input = request.form.get('email', '').strip()
        password = request.form.get('password')
        
        user = User.query.filter((User.email == login_input) | (User.username == login_input)).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'✓ Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        
        flash('❌ Неверный логин или пароль', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('❌ Пароли не совпадают', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('❌ Минимум 6 символов', 'error')
            return render_template('register.html')
        
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('❌ Логин или email занят', 'error')
            return render_template('register.html')
        
        try:
            db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password)))
            db.session.commit()
            flash('✓ Регистрация успешна! Войдите.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ошибка: {e}', 'error')
    
    return render_template('register.html')

@app.route('/profile')  # НОВЫЙ МАРШРУТ
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', orders=orders)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('✓ Вы вышли', 'info')
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/cart')
def cart():
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        subtotal = sum(item.product.price * item.quantity for item in cart_items)
    else:
        cart_items = []
        subtotal = 0
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        # Получаем данные из формы
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        
        # Получаем товары из корзины
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        
        if not cart_items:
            flash('Корзина пуста!', 'error')
            return redirect(url_for('catalog'))
        
        # Считаем общую сумму
        total = sum(item.product.price * item.quantity for item in cart_items)
        
        # Создаем заказ
        new_order = Order(
            user_id=current_user.id,
            total=total,
            status='new',  # Статус: новый
            created_at=datetime.utcnow()
        )
        db.session.add(new_order)
        db.session.flush()  # Получаем ID заказа
        
        # Создаем позиции заказа
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price
            )
            db.session.add(order_item)
            
            # Уменьшаем количество на складе
            item.product.stock -= item.quantity
        
        # Очищаем корзину
        for item in cart_items:
            db.session.delete(item)
        
        db.session.commit()
        
        flash(f'✓ Заказ #{new_order.id} оформлен! Мы свяжемся с вами.', 'success')
        return redirect(url_for('profile'))
    
    # GET запрос - показываем страницу оформления
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)


# ========================================
# АДМИН ПАНЕЛЬ
# ========================================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users_count = User.query.count()
    products_count = Product.query.count()
    orders_count = Order.query.count()
    # Общая выручка
    revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    
    return render_template('admin_dashboard.html', 
                           users_count=users_count, 
                           products_count=products_count, 
                           orders_count=orders_count,
                           revenue=revenue)

# --- УПРАВЛЕНИЕ ТОВАРАМИ ---
@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    products = Product.query.all()
    return render_template('admin_products.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_product():
    if request.method == 'POST':
        # Получаем данные из формы
        new_product = Product(
            name=request.form['name'],
            price=float(request.form['price']),
            image=request.form['image'],
            description=request.form['description'],
            stock=int(request.form['stock']),
            brand_id=1, # По умолчанию Nike (можно сделать выбор из списка)
            category_id=1 # По умолчанию Повседневные
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Товар успешно добавлен!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin_add_product.html')

@app.route('/admin/product/delete/<int:id>')
@login_required
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Товар удален.', 'info')
    return redirect(url_for('admin_products'))

# --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/toggle_admin/<int:id>')
@login_required
@admin_required
def admin_toggle_admin(id):
    user = User.query.get_or_404(id)
    if user != current_user: # Нельзя разжаловать себя самого
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f'Права пользователя {user.username} изменены.', 'success')
    return redirect(url_for('admin_users'))

# ==================== АДМИН ПАНЕЛЬ - ЗАКАЗЫ ====================

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/order/<int:order_id>')
@login_required
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('admin_order_detail.html', order=order)

@app.route('/admin/order/update_status/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    order.status = new_status
    db.session.commit()
    flash(f'Статус заказа #{order_id} обновлен на "{new_status}"', 'success')
    return redirect(url_for('admin_order_detail', order_id=order_id))

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================
def init_db():
    with app.app_context():
        db.create_all()
        if Product.query.first():
            print("✅ База уже наполнена.")
            return
            
        print("📦 Наполнение БД...")
        
        if Brand.query.count() == 0:
            db.session.add_all([
                Brand(name='Nike', slug='nike'),
                Brand(name='Adidas', slug='adidas'),
                Brand(name='Puma', slug='puma'),
                Brand(name='Reebok', slug='reebok'),
                Brand(name='Asics', slug='asics'),
                Brand(name='Balenciaga', slug='balenciaga'),
                Brand(name='New Balance', slug='new-balance')
            ])
            db.session.commit()
            
        if Category.query.count() == 0:
            db.session.add_all([
                Category(name='Повседневные', slug='everyday'),
                Category(name='Беговые', slug='running')
            ])
            db.session.commit()
            
        brands = {b.name: b.id for b in Brand.query.all()}
        cats = {c.name: c.id for c in Category.query.all()}
        
        # ВСЕ 22 ТОВАРА
        db.session.add_all([
            # 1-4: Оригинальные
            Product(name='Puma Suede XL', brand_id=brands['Puma'], category_id=cats['Повседневные'], price=8490, stock=50, sizes=[40,41,42,43,44,45], image='images/puma_suede_xl.jpg', description='Замшевые кроссовки.'),
            Product(name='Nike Air Max 90', brand_id=brands['Nike'], category_id=cats['Повседневные'], price=12990, stock=40, sizes=[40,41,42,43,44,45], image='images/nike_air_max_90.jpg', description='Легендарные Air Max 90.'),
            Product(name='Adidas Climacool', brand_id=brands['Adidas'], category_id=cats['Беговые'], price=9590, old_price=11990, stock=35, sizes=[40,41,42,43,44,45], image='images/adidas_climacool.jpg', description='Вентиляция 360°.'),
            Product(name='Adidas Supernova', brand_id=brands['Adidas'], category_id=cats['Беговые'], price=11490, old_price=13990, stock=45, sizes=[40,41,42,43,44,45], image='images/adidas_supernova.jpg', description='Амортизация Bounce.'),
            
            # 5-8: Дополнительные
            Product(name='Asics Gel-Kayano 29', brand_id=brands['Asics'], category_id=cats['Беговые'], price=14990, stock=30, sizes=[40,41,42,43,44,45], image='images/asics_gel_kayano.jpg', description='Премиальные беговые кроссовки.'),
            Product(name='Balenciaga Triple S', brand_id=brands['Balenciaga'], category_id=cats['Повседневные'], price=89990, stock=10, sizes=[40,41,42,43,44], image='images/balenciaga_triple_s.jpg', description='Икона уличной моды.'),
            Product(name='New Balance 574', brand_id=brands['New Balance'], category_id=cats['Повседневные'], price=10990, stock=40, sizes=[40,41,42,43,44,45], image='images/new_balance_574.jpg', description='Эталон стиля с 1988 года.'),
            Product(name='Reebok Classic Leather', brand_id=brands['Reebok'], category_id=cats['Повседневные'], price=8990, old_price=10990, stock=35, sizes=[40,41,42,43,44,45], image='images/reebok_classic.jpg', description='Легендарные кроссовки 1983 года.'),
            
            # 9-12: Еще товары
            Product(name='Nike Air Force 1', brand_id=brands['Nike'], category_id=cats['Повседневные'], price=11990, stock=55, sizes=[40,41,42,43,44,45], image='images/nike_air_force_1.jpg', description='Культовые кроссовки 1982 года.'),
            Product(name='Adidas Ultraboost 22', brand_id=brands['Adidas'], category_id=cats['Беговые'], price=16490, old_price=19990, stock=25, sizes=[40,41,42,43,44], image='images/adidas_ultraboost.jpg', description='Технология Boost.'),
            Product(name='Puma RS-X', brand_id=brands['Puma'], category_id=cats['Повседневные'], price=9990, old_price=13990, stock=30, sizes=[40,41,42,43,44,45], image='images/puma_rs_x.jpg', description='Яркий дизайн 80-х.'),
            Product(name='Nike React Infinity Run', brand_id=brands['Nike'], category_id=cats['Беговые'], price=13990, stock=35, sizes=[40,41,42,43,44,45], image='images/nike_react_infinity.jpg', description='Снижение риска травм.'),
            
            # 13-16: Еще
            Product(name='Asics Gel-Nimbus 24', brand_id=brands['Asics'], category_id=cats['Беговые'], price=15990, stock=20, sizes=[40,41,42,43,44], image='images/asics_gel_nimbus.jpg', description='Максимальный комфорт.'),
            Product(name='New Balance 990v5', brand_id=brands['New Balance'], category_id=cats['Повседневные'], price=18990, stock=15, sizes=[40,41,42,43,44,45], image='images/new_balance_990.jpg', description='Сделано в США.'),
            Product(name='Balenciaga Speed Trainer', brand_id=brands['Balenciaga'], category_id=cats['Повседневные'], price=69990, stock=8, sizes=[40,41,42,43], image='images/balenciaga_speed.jpg', description='Кроссовки-носки.'),
            Product(name='Reebok Pump Fury', brand_id=brands['Reebok'], category_id=cats['Повседневные'], price=12990, old_price=15990, stock=25, sizes=[40,41,42,43,44], image='images/reebok_pump_fury.jpg', description='Технология Pump.'),
            
            # 17-20: Дополнительные
            Product(name='Nike Air Max 270', brand_id=brands['Nike'], category_id=cats['Повседневные'], price=14990, stock=45, sizes=[40,41,42,43,44,45], image='images/nike_air_max_270.jpg', description='Максимальная воздушная подушка.'),
            Product(name='Adidas Yeezy Boost 350', brand_id=brands['Adidas'], category_id=cats['Повседневные'], price=24990, old_price=29990, stock=12, sizes=[40,41,42,43,44], image='images/adidas_yeezy_350.jpg', description='Культовая модель от Kanye West.'),
            Product(name='Puma Future Rider', brand_id=brands['Puma'], category_id=cats['Повседневные'], price=8990, stock=38, sizes=[40,41,42,43,44,45], image='images/puma_future_rider.jpg', description='Ретро-футуристический дизайн.'),
            Product(name='Asics Gel-Lyte III', brand_id=brands['Asics'], category_id=cats['Повседневные'], price=12990, stock=28, sizes=[40,41,42,43,44], image='images/asics_gel_lyte_3.jpg', description='Классика 1990 года.'),
            
            # 21-22: Последние
            Product(name='New Balance 327', brand_id=brands['New Balance'], category_id=cats['Повседневные'], price=11990, stock=42, sizes=[40,41,42,43,44,45], image='images/new_balance_327.jpg', description='Современная интерпретация 70-х.'),
            Product(name='Reebok Club C 85', brand_id=brands['Reebok'], category_id=cats['Повседневные'], price=9990, old_price=11990, stock=33, sizes=[40,41,42,43,44,45], image='images/reebok_club_c_85.jpg', description='Теннисная классика.')
        ])
        
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                email='admin@neowalk.local',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            ))
            print("✅ Админ: admin / admin123")
            
        db.session.commit()
        print("✅ Готово! Добавлено 22 товара.")

if __name__ == '__main__':
    init_db()
    
port = int(os.environ.get('PORT', 5001))
app.run(debug=False, host='0.0.0.0', port=port)