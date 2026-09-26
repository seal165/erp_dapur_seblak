import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- DETEKSI LINGKUNGAN (VERCEL / LOKAL) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IF_VERCEL = os.environ.get('VERCEL')

if IF_VERCEL:
    DB_PATH = '/tmp/database.db'
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception as e:
    print(f"Directory creation note: {e}")

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------------------------------------------------
# ROUTE KHUSUS UNTUK MENAMPILKAN GAMBAR (LOKAL & VERCEL FRIENDLY)
# -------------------------------------------------------------------
@app.route('/uploads/<filename>')
def send_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- FUNGSI PEMBERSIH FILE FOTO LAMA ---
def hapus_file_foto(filename):
    if filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

# -------------------------------------------------------------------
# MODEL DATABASE
# -------------------------------------------------------------------

class BahanBaku(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    harga_per_unit = db.Column(db.Float, nullable=False)
    uom = db.Column(db.String(20), nullable=False)
    gambar = db.Column(db.String(200), nullable=True)
    can_be_purchased = db.Column(db.Boolean, default=True)

class Produk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    harga_jual = db.Column(db.Float, nullable=False)
    gambar = db.Column(db.String(200), nullable=True)
    can_be_sold = db.Column(db.Boolean, default=True)
    resep_list = db.relationship('ResepBoM', backref='produk', cascade="all, delete-orphan", lazy=True)

    @property
    def total_modal(self):
        return sum(item.subtotal for item in self.resep_list)

class ResepBoM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produk_id = db.Column(db.Integer, db.ForeignKey('produk.id'), nullable=False)
    bahan_baku_id = db.Column(db.Integer, db.ForeignKey('bahan_baku.id'), nullable=False)
    kuantitas = db.Column(db.Float, nullable=False)

    bahan_baku = db.relationship('BahanBaku')

    @property
    def subtotal(self):
        if self.bahan_baku:
            return self.kuantitas * self.bahan_baku.harga_per_unit
        return 0.0

with app.app_context():
    db.create_all()

# -------------------------------------------------------------------
# ROUTE BAHAN BAKU
# -------------------------------------------------------------------

@app.route('/')
def index():
    return redirect(url_for('kelola_bahan_baku'))

@app.route('/bahan-baku', methods=['GET', 'POST'])
def kelola_bahan_baku():
    if request.method == 'POST':
        nama = request.form['nama']
        harga = float(request.form['harga'])
        uom = request.form['uom']
        
        filename = None
        if 'gambar' in request.files:
            file = request.files['gambar']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                except Exception:
                    pass
        
        bahan_baru = BahanBaku(nama=nama, harga_per_unit=harga, uom=uom, gambar=filename)
        db.session.add(bahan_baru)
        db.session.commit()
        return redirect(url_for('kelola_bahan_baku'))

    semua_bahan = BahanBaku.query.all()
    return render_template('bahan_baku.html', bahan_list=semua_bahan)

@app.route('/bahan-baku/edit/<int:id>', methods=['POST'])
def edit_bahan_baku(id):
    bahan = BahanBaku.query.get_or_404(id)
    bahan.nama = request.form['nama']
    bahan.harga_per_unit = float(request.form['harga'])
    bahan.uom = request.form['uom']
    
    if 'gambar' in request.files:
        file = request.files['gambar']
        if file and allowed_file(file.filename):
            hapus_file_foto(bahan.gambar)
            
            filename = secure_filename(file.filename)
            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bahan.gambar = filename
            except Exception:
                pass

    db.session.commit()
    return redirect(url_for('kelola_bahan_baku'))

@app.route('/bahan-baku/delete/<int:id>', methods=['POST'])
def delete_bahan_baku(id):
    bahan = BahanBaku.query.get_or_404(id)
    hapus_file_foto(bahan.gambar)
    
    db.session.delete(bahan)
    db.session.commit()
    return redirect(url_for('kelola_bahan_baku'))

# -------------------------------------------------------------------
# ROUTE PRODUK & RESEP
# -------------------------------------------------------------------

@app.route('/produk', methods=['GET', 'POST'])
def kelola_produk():
    if request.method == 'POST':
        nama = request.form['nama']
        harga_jual = float(request.form['harga_jual'])
        
        filename = None
        if 'gambar' in request.files:
            file = request.files['gambar']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                except Exception:
                    pass

        produk_baru = Produk(nama=nama, harga_jual=harga_jual, gambar=filename)
        db.session.add(produk_baru)
        db.session.commit()
        return redirect(url_for('kelola_produk'))

    semua_produk = Produk.query.all()
    semua_bahan = BahanBaku.query.all()
    return render_template('produk.html', produk_list=semua_produk, bahan_list=semua_bahan)

@app.route('/produk/edit/<int:id>', methods=['POST'])
def edit_produk(id):
    produk = Produk.query.get_or_404(id)
    produk.nama = request.form['nama']
    produk.harga_jual = float(request.form['harga_jual'])
    
    if 'gambar' in request.files:
        file = request.files['gambar']
        if file and allowed_file(file.filename):
            hapus_file_foto(produk.gambar)
            
            filename = secure_filename(file.filename)
            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                produk.gambar = filename
            except Exception:
                pass

    db.session.commit()
    return redirect(url_for('kelola_produk'))

@app.route('/produk/delete/<int:id>', methods=['POST'])
def delete_produk(id):
    produk = Produk.query.get_or_404(id)
    hapus_file_foto(produk.gambar)
    
    db.session.delete(produk)
    db.session.commit()
    return redirect(url_for('kelola_produk'))

@app.route('/tambah-resep/<int:produk_id>', methods=['POST'])
def tambah_resep(produk_id):
    bahan_id = int(request.form['bahan_id'])
    kuantitas = float(request.form['kuantitas'])

    resep_baru = ResepBoM(produk_id=produk_id, bahan_baku_id=bahan_id, kuantitas=kuantitas)
    db.session.add(resep_baru)
    db.session.commit()
    return redirect(url_for('kelola_produk'))

@app.route('/resep/delete/<int:resep_id>', methods=['POST'])
def delete_resep(resep_id):
    resep = ResepBoM.query.get_or_404(resep_id)
    db.session.delete(resep)
    db.session.commit()
    return redirect(url_for('kelola_produk'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)