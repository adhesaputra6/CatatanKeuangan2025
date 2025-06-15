import os
import logging
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue, MessageHandler, filters
import json
import threading
import time

# === Logging Setup ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Flask Keep-Alive Server (Opsional) ===
try:
    from flask import Flask
except ImportError:
    os.system("pip install flask")
    from flask import Flask

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

# === Tabungan Module – Simpan per Chat ID ===
TABUNGAN_GAJI_FILE = "data/nabunggaji.json"
TABUNGAN_MANUAL_FILE = "data/nabungmanual.json"
AMBIL_TABUNGAN_FILE = "data/ambiltabungan.json"

os.makedirs("data", exist_ok=True)

if not os.path.exists(TABUNGAN_GAJI_FILE):
    with open(TABUNGAN_GAJI_FILE, 'w') as f:
        json.dump({}, f)

if not os.path.exists(TABUNGAN_MANUAL_FILE):
    with open(TABUNGAN_MANUAL_FILE, 'w') as f:
        json.dump({}, f)

if not os.path.exists(AMBIL_TABUNGAN_FILE):
    with open(AMBIL_TABUNGAN_FILE, 'w') as f:
        json.dump({}, f)

# Fungsi untuk Nabung Gaji
def load_nabunggaji():
    with open(TABUNGAN_GAJI_FILE, 'r') as f:
        return json.load(f)

def save_nabunggaji(data):
    with open(TABUNGAN_GAJI_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_nabunggaji(chat_id):
    data = load_nabunggaji()
    return int(data.get(str(chat_id), 0))

def add_nabunggaji(chat_id, jumlah):
    chat_id_str = str(chat_id)
    data = load_nabunggaji()
    data[chat_id_str] = int(data.get(chat_id_str, 0)) + jumlah
    save_nabunggaji(data)

# Fungsi untuk Nabung Manual
def load_nabungmanual():
    with open(TABUNGAN_MANUAL_FILE, 'r') as f:
        return json.load(f)

def save_nabungmanual(data):
    with open(TABUNGAN_MANUAL_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_nabungmanual(chat_id):
    data = load_nabungmanual()
    return int(data.get(str(chat_id), 0))

def add_nabungmanual(chat_id, jumlah):
    chat_id_str = str(chat_id)
    data = load_nabungmanual()
    data[chat_id_str] = int(data.get(chat_id_str, 0)) + jumlah
    save_nabungmanual(data)

# Fungsi untuk Ambil Tabungan
def load_ambiltabungan():
    with open(AMBIL_TABUNGAN_FILE, 'r') as f:
        return json.load(f)

def save_ambiltabungan(data):
    with open(AMBIL_TABUNGAN_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_ambiltabungan(chat_id):
    data = load_ambiltabungan()
    return int(data.get(str(chat_id), 0))

def add_ambiltabungan(chat_id, jumlah):
    chat_id_str = str(chat_id)
    data = load_ambiltabungan()
    data[chat_id_str] = int(data.get(chat_id_str, 0)) + jumlah
    save_ambiltabungan(data)

# === SQLite Setup – Per User Database ===
try:
    from sqlalchemy import create_engine, Column, Integer, String, Float, Date
    from sqlalchemy.orm import declarative_base, sessionmaker
except ImportError:
    os.system("pip install sqlalchemy")
    from sqlalchemy import create_engine, Column, Integer, String, Float, Date
    from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Transaksi(Base):
    __tablename__ = 'transaksi'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tanggal = Column(Date)
    kategori = Column(String)
    tipe = Column(String)
    nominal = Column(Float)
    keterangan = Column(String)

# Dictionary untuk session per user
user_sessions = {}

def get_session(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str in user_sessions:
        return user_sessions[chat_id_str]

    db_path = f"data/user_{chat_id_str}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user_sessions[chat_id_str] = session
    return session

# === Authorized Users via DB ===
AUTHORIZED_USERS_FILE = "data/users.json"

if not os.path.exists(AUTHORIZED_USERS_FILE):
    with open(AUTHORIZED_USERS_FILE, 'w') as f:
        json.dump({"admin": "secret123"}, f)

def load_users():
    with open(AUTHORIZED_USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(AUTHORIZED_USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

AUTHORIZED_USERS = load_users()
OWNER_ID = int(os.getenv("OWNER_ID"))

# === Login System ===

AUTHORIZED_USERS = load_users()  # Dari users.json

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id

    if chat_id == OWNER_ID:
        context.user_data["authorized"] = True
        context.user_data["user"] = {"username": "owner", "role": "admin"}
        await update.message.reply_text("👑 Anda adalah Owner! Auto-login sebagai admin.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("❌ Format salah.\nGunakan: /login username token")
        return

    username, token = context.args
    users = load_users()

    if users.get(username) == token:
        context.user_data["authorized"] = True
        context.user_data["user"] = {"username": username, "role": "user"}

        # Kirim info ke Owner
        owner_message = (
            f"🔔 *User Login*\n"
            f"👤 Username: `{username}`\n"
            f"📱 Chat ID: `{chat_id}`\n"
            f"📅 Tanggal: {datetime.date.today().strftime('%Y-%m-%d')}"
        )
        await notify_owner(context, owner_message)

        await update.message.reply_text("✅ Login berhasil!")
    else:
        await update.message.reply_text("❌ Username atau token salah.")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("authorized"):
        context.user_data["authorized"] = False
        await update.message.reply_text("👋 Logout berhasil.")
    else:
        await update.message.reply_text("❌ Anda belum login.")

# === Daily Reminder via JobQueue ===
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = int(os.getenv("CHAT_ID"))
    if not chat_id:
        logger.warning("CHAT_ID tidak ditemukan di .env")
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text="🔔 Jangan lupa catat transaksi hari ini!")
    except Exception as e:
        logger.error(f"❌ Gagal kirim notifikasi harian: {e}")

def run_scheduler(application):
    application.job_queue.run_daily(daily_reminder, days=tuple(range(7)), time=datetime.time(hour=9, minute=0))
    logger.info("⏰ Notifikasi harian diatur: Jam 09:00")

# === Saldo – Dihitung dari riwayat lokal ===
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    try:
        session = get_session(update.effective_user.id)
        data = session.query(Transaksi).all()
        total_masuk = sum(t.nominal for t in data if t.tipe == "Pemasukan")
        total_keluar = sum(t.nominal for t in data if t.tipe == "Pengeluaran")
        total_saldo = total_masuk - total_keluar
        await update.message.reply_text(f"💰 Saldo saat ini: Rp{total_saldo}")
    except Exception as e:
        logger.error(f"Error saat cek saldo: {e}")
        await update.message.reply_text("❌ Tidak bisa membaca data saldo.")

# === Bulanan – Menampilkan Total Masuk/Keluar/Bulan Ini ===
async def bulan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    try:
        now = datetime.datetime.now()
        session = get_session(update.effective_user.id)
        data = session.query(Transaksi).all()
        message = "🗓️ Transaksi Bulan Ini:\n"
        count = 0
        total_masuk = 0
        total_keluar = 0
        for row in data:
            if row.tanggal.year == now.year and row.tanggal.month == now.month:
                count += 1
                if row.tipe == "Pemasukan":
                    total_masuk += int(row.nominal)
                elif row.tipe == "Pengeluaran":
                    total_keluar += int(row.nominal)
                message += f"{count}. {row.tanggal.strftime('%Y-%m-%d')} | {row.tipe} | Rp{int(row.nominal)} | {row.kategori} | {row.keterangan}\n"

        if count == 0:
            await update.message.reply_text("📊 Tidak ada transaksi dalam bulan ini.")
            return

        message += f"\n\n📥 Total Pemasukan: Rp{total_masuk}"
        message += f"\n📤 Total Pengeluaran: Rp{total_keluar}"
        message += f"\n💰 Saldo Bulan Ini: Rp{total_masuk - total_keluar}"
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error saat menampilkan bulan: {e}")
        await update.message.reply_text("❌ Tidak bisa menampilkan transaksi bulan ini.")

# === Masuk/Keluar – Simpan ke Lokal SQLite ===
async def masuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    try:
        if len(context.args) < 3:
            raise ValueError("Argumen tidak lengkap.")
        nominal = int(context.args[0])
        kategori = context.args[1]
        keterangan = ' '.join(context.args[2:])
        chat_id = update.effective_user.id
        tanggal = datetime.date.today()

        session = get_session(chat_id)
        session.add(Transaksi(
            tanggal=tanggal,
            kategori=kategori,
            tipe="Pemasukan",
            nominal=nominal,
            keterangan=keterangan
        ))
        session.commit()
        await update.message.reply_text(f"✅ Pemasukan Rp{nominal} ditambahkan.")
    except IndexError:
        await update.message.reply_text("❌ Format salah.\nContoh: /masuk 50000 Gaji Bonus Mei")
    except ValueError:
        await update.message.reply_text("❌ Masukkan nominal berupa angka.")
    except Exception as e:
        logger.error(f"Error saat pemasukan: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan.")

async def keluar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    try:
        if len(context.args) < 3:
            raise ValueError("Argumen tidak lengkap.")
        nominal = int(context.args[0])
        kategori = context.args[1]
        keterangan = ' '.join(context.args[2:])
        chat_id = update.effective_user.id
        tanggal = datetime.date.today()

        session = get_session(chat_id)
        session.add(Transaksi(
            tanggal=tanggal,
            kategori=kategori,
            tipe="Pengeluaran",
            nominal=nominal,
            keterangan=keterangan
        ))
        session.commit()
        await update.message.reply_text(f"✅ Pengeluaran Rp{nominal} ditambahkan.")
    except IndexError:
        await update.message.reply_text("❌ Format salah.\nContoh: /keluar 30000 Makan Nasi Padang")
    except ValueError:
        await update.message.reply_text("❌ Masukkan nominal berupa angka.")
    except Exception as e:
        logger.error(f"Error saat pengeluaran: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan.")

# === Delete Baris Langsung Tanpa Konfirmasi ===
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    try:
        baris = int(context.args[0])
        chat_id = update.effective_user.id
        session = get_session(chat_id)
        data = session.query(Transaksi).all()

        if baris < 1 or baris > len(data):
            await update.message.reply_text(f"❌ Baris tidak valid. Harus antara 1 hingga {len(data)}")
            return

        selected = data[baris - 1]
        session.delete(selected)
        session.commit()
        await update.message.reply_text(f"🗑️ Data baris {baris} telah dihapus.")
    except IndexError:
        await update.message.reply_text("❌ Masukkan nomor baris yang ingin dihapus.")
    except ValueError:
        await update.message.reply_text("❌ Masukkan hanya angka sebagai nomor baris.")
    except Exception as e:
        logger.error(f"Error saat hapus: {e}")
        await update.message.reply_text("❌ Gagal menghapus baris.")

# === Clear Semua Riwayat Chat dan Data Lokal ===
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return

    # Cek apakah sudah dalam mode konfirmasi
    if context.user_data.get("confirm_clear", False) is False:
        context.user_data["confirm_clear"] = True
        await update.message.reply_text("⚠️ Apakah Anda yakin ingin menghapus semua riwayat Transaksi? Data tabungan tidak akan terhapus (y/n)")
        return

    jawaban = context.args[0].lower() if context.args else update.message.text.lower()

    if jawaban == 'y':
        chat_id = update.effective_user.id
        session = get_session(chat_id)
        try:
            session.query(Transaksi).delete()
            session.commit()

            # Reset semua file tabungan
            with open(NABUNGGAJI_FILE, 'r+') as f:
                data = json.load(f)
                data[str(chat_id)] = 0
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

            with open(NABUNGLAIN_FILE, 'r+') as f:
                data = json.load(f)
                data[str(chat_id)] = 0
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

            with open(AMBILTABUNGAN_FILE, 'r+') as f:
                data = json.load(f)
                data[str(chat_id)] = 0
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

            context.user_data["confirm_clear"] = False
            await update.message.reply_text("🧹 Semua riwayat Transaksi lokal berhasil dihapus.")
        except Exception as e:
            context.user_data["confirm_clear"] = False
            logger.error(f"❌ Gagal membersihkan Transaksi: {e}")
            await update.message.reply_text("❌ Gagal membersihkan Transaksi.")
    elif jawaban == 'n':
        context.user_data["confirm_clear"] = False
        await update.message.reply_text("🛑 Penghapusan dibatalkan.")
    else:
        await update.message.reply_text("❌ Harap ketik 'y' atau 'n'.")

#=== Handle Clear Confirmation ===

async def handle_clear_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jawaban = update.message.text.strip().lower()

    if jawaban == 'y' and context.user_data.get("confirm_clear", False):
        chat_id = update.effective_user.id

        # Hapus semua data transaksi SQLite
        session = get_session(chat_id)
        session.query(Transaksi).delete()
        session.commit()

        # Kirim konfirmasi
        await update.message.reply_text("🧹 Semua riwayat Transaksi berhasil dihapus.")
        context.user_data["confirm_clear"] = False

    elif jawaban == 'n' and context.user_data.get("confirm_clear", False):
        await update.message.reply_text("🛑 Penghapusan dibatalkan.")
        context.user_data["confirm_clear"] = False

    else:
        await update.message.reply_text("❌ Harap ketik 'y' atau 'n'.")

# === Laporan PDF Export ===
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
except ImportError:
    os.system("pip install reportlab")
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

try:
    from openpyxl import Workbook
except ImportError:
    os.system("pip install openpyxl")
    from openpyxl import Workbook

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return

    try:
        chat_id = update.effective_user.id
        session = get_session(chat_id)
        data = session.query(Transaksi).all()[-20:]

        pdf_path = f"reports/report_{chat_id}_{datetime.date.today()}.pdf"
        doc = SimpleDocTemplate(pdf_path)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Laporan Keuangan Harian", styles['Title']))
        elements.append(Spacer(1, 24))
        table_data = [["Tanggal", "Kategori", "Tipe", "Nominal", "Keterangan"]]
        for row in data:
            table_data.append([
                row.tanggal.strftime("%Y-%m-%d"),
                row.kategori,
                row.tipe,
                str(int(row.nominal)),
                row.keterangan
            ])
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), '#cccccc'),
            ('GRID', (0, 0), (-1, -1), 1, '#000000')
        ]))
        elements.append(t)
        doc.build(elements)

        excel_path = f"reports/excel_{chat_id}_{datetime.date.today()}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Laporan Keuangan"
        ws.append(["Tanggal", "Kategori", "Tipe", "Nominal", "Keterangan"])
        for row in data:
            ws.append([
                row.tanggal.strftime("%Y-%m-%d"),
                row.kategori,
                row.tipe,
                str(int(row.nominal)),
                row.keterangan
            ])
        wb.save(excel_path)

        with open(pdf_path, 'rb') as f_pdf, open(excel_path, 'rb') as f_excel:
            await update.message.reply_document(document=f_pdf, filename=os.path.basename(pdf_path))
            await update.message.reply_document(document=f_excel, filename=os.path.basename(excel_path))

    except Exception as e:
        logger.error(f"❌ Gagal membuat laporan: {e}")
        await update.message.reply_text("❌ Gagal menghasilkan laporan.")

# === Start Menu ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang di Bot Catatan Keuangan!\n"
        "Perintah tersedia:\n"
        "/login username password\n"
        "/logout → keluar dari sesi\n"
        "/masuk nominal kategori keterangan\n"
        "/keluar nominal kategori keterangan\n"
        "/saldo → Untuk melihat sisa uang\n"
        "/bulan → Rincian semua transaksi bulan ini\n"
        "/laporan → Output PDF & Excel\n"
        "/clear ← Hapus semua Transaksi kecuali Tabungan\n"
        "/delete baris\n"
        "\n💰 Tabungan:\n"
        "/lihattabungan → Lihat tabungan pribadi\n"
        "/nabunggaji jumlah → Menabung dari gaji (saldo utama berkurang)\n"
        "/nabunglain jumlah → Menabung dari luar gaji (tidak mengurangi saldo utama)\n"
        "/ambiltabungan jumlah → Ambil uang dari tabungan\n"        
    )

# === Fitur Tabungan Tambahan ===

async def lihattabungan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return

    chat_id = str(update.effective_user.id)
    today = datetime.date.today().strftime("%Y-%m-%d")

    # Baca semua file JSON
    nabung_gaji = get_nabunggaji(chat_id)
    nabung_manual = get_nabungmanual(chat_id)
    ambil = get_ambiltabungan(chat_id)

    total_tabungan = nabung_gaji + nabung_manual - ambil

    pesan = (
        f"📅 Tanggal: {today}\n\n"
        f"📥 Total Nabung dari Gaji: Rp{nabung_gaji:,}\n"
        f"📥 Total Nabung Manual: Rp{nabung_manual:,}\n"
        f"📤 Total Penarikan: Rp{ambil:,}\n"
        f"💰 Sisa Tabungan: Rp{total_tabungan:,}\n\n"
        f"*Rincian Transaksi Tabungan Anda*\n"
    )

    # Rincian transaksi dari file JSON
    try:
        with open("data/nabunggaji.json", "r") as f:
            data_gaji = json.load(f)
        with open("data/nabungmanual.json", "r") as f:
            data_manual = json.load(f)
        with open("data/ambiltabungan.json", "r") as f:
            data_ambil = json.load(f)

        # Rincian Nabung dari Gaji
        if chat_id in data_gaji and data_gaji[chat_id] > 0:
            pesan += "\n📥 *Nabung dari Gaji*:\n"
            pesan += f"• Rp{data_gaji[chat_id]:,}\n"

        # Rincian Nabung Manual
        if chat_id in data_manual and data_manual[chat_id] > 0:
            pesan += "\n📥 *Nabung Manual*:\n"
            pesan += f"• Rp{data_manual[chat_id]:,}\n"

        # Rincian Penarikan
        if chat_id in data_ambil and data_ambil[chat_id] > 0:
            pesan += "\n📤 *Penarikan Tabungan*:\n"
            pesan += f"• Rp{data_ambil[chat_id]:,}\n"

    except Exception as e:
        logger.warning(f"⚠️ Tidak bisa baca rincian tabungan: {e}")
        pesan += "\n⚠️ Tidak ada rincian tabungan."

    await update.message.reply_text(pesan.strip(), parse_mode="Markdown")

# === Nabung dari Gaji (mengurangi saldo utama) ===
async def nabunggaji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Format salah.\nContoh: /nabunggaji 5000")
        return
    try:
        jumlah = int(context.args[0])
        chat_id = update.effective_user.id
        if jumlah <= 0:
            await update.message.reply_text("❌ Jumlah harus lebih besar dari nol.")
            return

        # Tambahkan ke tabungan gaji
        add_nabunggaji(chat_id, jumlah)

        # Kurangi saldo utama
        session = get_session(chat_id)
        session.add(Transaksi(
            tanggal=datetime.date.today(),
            kategori="Tabungan",
            tipe="Pengeluaran",
            nominal=jumlah,
            keterangan="Nabung dari gaji"
        ))
        session.commit()

        # Hitung ulang
        data_transaksi = session.query(Transaksi).all()
        total_masuk = sum(t.nominal for t in data_transaksi if t.tipe == "Pemasukan")
        total_keluar = sum(t.nominal for t in data_transaksi if t.tipe == "Pengeluaran")
        total_saldo = total_masuk - total_keluar
        total_tabungan_sekarang = get_nabunggaji(chat_id) + get_nabungmanual(chat_id) - get_ambiltabungan(chat_id)

        await update.message.reply_text(f"✅ Berhasil menabung dari gaji sebesar Rp{jumlah}. Saldo utama berkurang.")
        await update.message.reply_text(f"💸 Sisa Saldo Utama: Rp{int(total_saldo)}")
        await update.message.reply_text(f"💰 Sisa Tabungan: Rp{int(total_tabungan_sekarang)}")
    except ValueError:
        await update.message.reply_text("❌ Masukkan nominal berupa angka.")

# === Nabung Manual (Tidak Mengurangi Saldo Utama) ===
async def nabunglain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Format salah.\nContoh: /nabunglain 5000")
        return
    try:
        jumlah = int(context.args[0])
        chat_id = update.effective_user.id
        if jumlah <= 0:
            await update.message.reply_text("❌ Jumlah harus lebih besar dari nol.")
            return

        add_nabungmanual(chat_id, jumlah)
        total_tabungan = get_nabunggaji(chat_id) + get_nabungmanual(chat_id)

        await update.message.reply_text(f"✅ Berhasil menabung dari luar gaji sebesar Rp{jumlah}. Saldo utama tidak berkurang.")
        await update.message.reply_text(f"💰 Total tabungan Anda sekarang: Rp{total_tabungan}")
    except ValueError:
        await update.message.reply_text("❌ Masukkan nominal berupa angka.")
    except Exception as e:
        logger.error(f"Error saat menabung dari luar gaji: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan.")

# === Ambil Tabungan (dari total tabungan) ===
async def ambiltabungan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("❌ Anda belum login.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Format salah.\nContoh: /ambiltabungan 2000")
        return
    try:
        jumlah = int(context.args[0])
        chat_id = update.effective_user.id
        if jumlah <= 0:
            await update.message.reply_text("❌ Jumlah harus lebih besar dari nol.")
            return

        # Cek apakah cukup tabungan
        total_gaji = get_nabunggaji(chat_id)
        total_manual = get_nabungmanual(chat_id)
        total_ditabung = total_gaji + total_manual
        total_diambil = get_ambiltabungan(chat_id)

        if jumlah > (total_ditabung - total_diambil):
            await update.message.reply_text("❌ Saldo tabungan tidak mencukupi.")
            return

        # Catat penarikan sebagai pemasukan baru
        session = get_session(chat_id)
        session.add(Transaksi(
            tanggal=datetime.date.today(),
            kategori="Tabungan",
            tipe="Pemasukan",
            nominal=jumlah,
            keterangan="Penarikan tabungan"
        ))
        session.commit()

        # Tambahkan jumlah yang diambil
        add_ambiltabungan(chat_id, jumlah)

        # Hitung ulang
        data = session.query(Transaksi).all()
        total_masuk = sum(t.nominal for t in data if t.tipe == "Pemasukan")
        total_keluar = sum(t.nominal for t in data if t.tipe == "Pengeluaran")
        total_saldo = total_masuk - total_keluar
        sisa_tabungan = total_gaji + total_manual - get_ambiltabungan(chat_id)

        await update.message.reply_text(f"✅ Berhasil mengambil Rp{jumlah} dari tabungan.")
        await update.message.reply_text(f"💸 Saldo utama sekarang: Rp{int(total_saldo)}")
        await update.message.reply_text(f"💰 Sisa tabungan Anda sekarang: Rp{sisa_tabungan}")
    except ValueError:
        await update.message.reply_text("❌ Masukkan nominal berupa angka.")

# === Fungsi Manajemen User ===
async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner yang bisa menambahkan user.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Format salah.\nContoh: /adduser username token")
        return

    username, token = context.args
    users = load_users()
    if username in users:
        await update.message.reply_text(f"❌ Username `{username}` sudah ada.", parse_mode="Markdown")
        return

    users[username] = token
    save_users(users)
    await update.message.reply_text(f"✅ Berhasil menambahkan user baru: `{username}`", parse_mode="Markdown")

async def hapususer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner yang bisa menghapus user.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Format salah.\nContoh: /hapususer username")
        return

    username = context.args[0]
    users = load_users()
    if username not in users:
        await update.message.reply_text("❌ User tidak ditemukan.")
        return

    del users[username]
    save_users(users)
    await update.message.reply_text(f"🗑️ Berhasil menghapus user: `{username}`", parse_mode="Markdown")

async def listuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner yang bisa melihat daftar user.")
        return

    users = load_users()
    message = "👥 Daftar User:\n"
    for idx, (username, _) in enumerate(users.items(), start=1):
        message += f"{idx}. {username}\n"

    if not users:
        message = "⚠️ Tidak ada user yang terdaftar."

    await update.message.reply_text(message)

# === Bantuan ===
async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pesan = (
        "📘 *DAFTAR PERINTAH BOT*\n\n"
        "🔐 *Autentikasi*\n"
        "/login username token → Login ke akun\n"
        "/logout → Keluar dari sesi\n\n"

        "📥 *Transaksi Keuangan*\n"
        "/masuk nominal kategori keterangan → Tambahkan pemasukan\n"
        "/keluar nominal kategori keterangan → Tambahkan pengeluaran\n"
        "/saldo → Cek saldo utama (pemasukan - pengeluaran)\n"
        "/bulan → Rincian transaksi bulan ini + total masuk/keluar\n"
        "/delete baris → Hapus satu baris riwayat\n"
        "/clear → Hapus semua riwayat Transaksi \n"
        "/laporan → Output PDF & Excel\n\n"

        "💰 *Fitur Tabungan*\n"
        "/lihattabungan → Lihat rincian tabungan\n"
        "/nabunggaji jumlah → Menabung dari gaji (saldo utama berkurang)\n"
        "/nabunglain jumlah → Menabung diluar gaji (saldo utama tidak berkurang)\n"
        "/ambiltabungan jumlah → Ambil uang dari tabungan\n\n"

        "🔔 *Bantuan & Informasi*\n"
        "/bantuan → Melihat daftar perintah\n\n"
        f"📞 Hubungi Owner: t.me/adesaputra6\n" #`{OWNER_ID}`
    )
    await update.message.reply_text(pesan, parse_mode="Markdown")

# === Fungsi Tambahan Notifikasi ke Owner ===
async def notify_owner(context: ContextTypes.DEFAULT_TYPE, message: str):
    owner_id = int(os.getenv("OWNER_ID"))
    try:
        await context.bot.send_message(chat_id=owner_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ Gagal kirim notifikasi ke Owner: {e}")

# === Unknown Command Handler ===
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Tidak mengenali perintah ini.\n"
        "Ketik /bantuan untuk melihat daftar perintah."
    )

# === Main Function ===
if __name__ == '__main__':
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    logger.info("🟢 Flask server dimulai di http://localhost:8000")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    if not BOT_TOKEN:
        logger.critical("❌ BOT_TOKEN tidak ditemukan di environment variables.")
        exit(1)

    job_queue = JobQueue()
    application = ApplicationBuilder().token(BOT_TOKEN).job_queue(job_queue).build()

    handlers = [
        CommandHandler("start", start),
        CommandHandler("login", login),
        CommandHandler("logout", logout),
        CommandHandler("masuk", masuk),
        CommandHandler("keluar", keluar),
        CommandHandler("saldo", saldo),
        CommandHandler("bulan", bulan),
        CommandHandler("laporan", laporan),
        CommandHandler("delete", delete),
        CommandHandler("clear", clear),
        CommandHandler("lihattabungan", lihattabungan),
        CommandHandler("adduser", adduser),
        CommandHandler("hapususer", hapususer),
        CommandHandler("listuser", listuser),
        CommandHandler("nabunggaji", nabunggaji),
        CommandHandler("nabunglain", nabunglain),
        CommandHandler("ambiltabungan", ambiltabungan),
        CommandHandler("bantuan", bantuan),
    ]
    for handler in handlers:
        application.add_handler(handler)

    # Handler untuk pesan clear #
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_clear_confirmation))

    # Handler command tidak dikenali
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    run_scheduler(application)

    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        try:
            logger.info("🟢 Memulai polling bot...")
            application.run_polling()
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"⚠️ Bot crash. Mencoba restart ulang ({retry_count}/{max_retries})...")
            time.sleep(5 * retry_count)
    else:
        logger.critical("🔴 Bot gagal dijalankan setelah beberapa kali percobaan.")