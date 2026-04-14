from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from models import User, Product, Brand, Category, CartItem, Order, OrderItem
from extensions import db, login_manager
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'neowalk-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///neowalk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.route('/product/<int:product_id>')
def product(product_id):
    prod = Product.query.get_or_404(product_id)
    return render_template('product.html', product=prod)

@app.route('/cart')
def cart():
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        subtotal = sum(item.product.price * item.quantity for item in cart_items)
    else:
        cart_items, subtotal = [], 0
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if not current_user.is_authenticated:
        flash('Войдите, чтобы добавить товар', 'error')
        return redirect(url_for('login'))
    qty = int(request.form.get('quantity', 1))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += qty
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=qty))
    db.session.commit()
    flash('Добавлено в корзину', 'success')
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

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if item:
            db.session.delete(item)
            db.session.commit()
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
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'error')
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
        if password != confirm or len(password) < 6:
            flash('Ошибка валидации', 'error')
            return render_template('register.html')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Логин или email занят', 'error')
            return render_template('register.html')
        try:
            db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password)))
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {e}', 'error')
    return render_template('register.html')

@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', orders=orders)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/products')
@login_required
def admin_products():
    products = Product.query.all()
    return render_template('admin_products.html', products=products)

@app.route('/admin/orders')
@login_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

def init_db():
    with app.app_context():
        db.create_all()
        if Product.query.first():
            return
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
        db.session.add_all([
            Product(name='Puma Suede XL', brand_id=brands['Puma'], category_id=cats['Повседневные'], price=8490, stock=50, image='images/puma_suede_xl.jpg', description='Замшевые кроссовки.'),
            Product(name='Nike Air Max 90', brand_id=brands['Nike'], category_id=cats['Повседневные'], price=12990, stock=40, image='images/nike_air_max_90.jpg', description='Легендарные Air Max 90.'),
            Product(name='Adidas Climacool', brand_id=brands['Adidas'], category_id=cats['Беговые'], price=9590, old_price=11990, stock=35, image='images/adidas_climacool.jpg', description='Вентиляция 360°.'),
            Product(name='Adidas Supernova', brand_id=brands['Adidas'], category_id=cats['Беговые'], price=11490, old_price=13990, stock=45, image='images/adidas_supernova.jpg', description='Амортизация Bounce.')
        ])
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', email='admin@neowalk.local', password_hash=generate_password_hash('admin123'), is_admin=True))
        db.session.commit()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)