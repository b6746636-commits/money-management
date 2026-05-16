import os
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, url_for, session  # 👈 เพิ่ม session ตรงนี้
from supabase import create_client

app = Flask(__name__)
app.secret_key = "super_secret_key_for_flash_messages"

# 🔑 ตั้งรหัสผ่านสำหรับแอดมินที่นี่
ADMIN_PASSWORD = "your_admin_password_here" 

# 👥 1. ฟิกรายชื่อคนที่มีสิทธิ์จ่ายเงินไว้ที่นี่ (แก้ไขตามชื่อจริงได้เลยครับ)
ALLOWED_NAMES = [
    # รุ่น 14
    "เหมยเหมย", "วุ้นเป็ด", "กาฟิว", "ไฟท์", "กัน", "ต้นข้าว", "แอน", "น้ำมนต์", 
    "เนส", "จ๊ะจ๋า", "แพนเค้ก", "อาคลัง", "โอม", "เอ็มมี่", "กีตาร์", "หมูอ้วน", "อุ๋มอิ๋ม", "ปัญปัญ",
    
    # รุ่น 15
    "นุ่น", "จ้าว", "โฟร์", "ลูกไหม", "ออย", "ปอแก้ว", "เชอร์รี่", "สารวัตร", "ฟีฟ่า", 
    "มาร์ติน", "ปังปัง", "ฟลุ๊ก", "พีเจ", "ฟิล์ม", "เฟรม"
]

# --- 🔌 เชื่อมต่อ Supabase ---
SUPABASE_URL = "https://atnjjcdcaxuqbzzzhloy.supabase.co"
SUPABASE_KEY = "รหัส_service_role_ของคุณ" 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "payment-slips"  

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- หน้าแรก (ส่งฟอร์มสลิปอย่างเดียว / ไม่แสดงตารางให้คนทั่วไปเห็น) ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        file = request.files.get("slip")

        if not name or not amount or not file or file.filename == "":
            flash("❌ กรุณากรอกข้อมูลและแนบสลิปให้ครบถ้วน", "danger")
            return redirect(url_for("index"))

        # 🚨 ตรวจสอบว่าชื่อที่พิมพ์มา ตรงกับชื่อที่ฟิกไว้ในระบบไหม
        if name not in ALLOWED_NAMES:
            flash("❌ ไม่พบชื่อของคุณในระบบ กรุณาตรวจสอบการพิมพ์สะกดคำ", "danger")
            return redirect(url_for("index"))

        if file and allowed_file(file.filename):
            file_ext = file.filename.rsplit(".", 1)[1].lower()
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_name = name.replace(" ", "_")
            filename = f"{current_time}_{clean_name}.{file_ext}"

            try:
                file_data = file.read()
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=filename,
                    file=file_data,
                    file_options={"content-type": file.content_type},
                )
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)

                data = {
                    "name": name,
                    "amount": float(amount),
                    "slip_url": public_url,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                supabase.table("payments").insert(data).execute()

                flash("🎉 อัปโหลดสลิปแจ้งชำระเงินสำเร็จแล้ว!", "success")
                return redirect(url_for("index"))

            except Exception as e:
                flash(f"เกิดข้อผิดพลาด: {e}", "danger")
                return redirect(url_for("index"))
        else:
            flash("❌ รูปภาพต้องเป็นนามสกุล png, jpg, jpeg, gif เท่านั้น", "danger")
            return redirect(url_for("index"))

    # ส่งรายชื่อที่ฟิกไว้ไปทำ Dropdown (Select Option) ในหน้าเว็บด้วย
    return render_template("index.html", allowed_names=ALLOWED_NAMES)


# --- หน้าสำหรับแอดมินล็อกอินเข้าดูข้อมูล ---
@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            flash("❌ รหัสผ่านแอดมินไม่ถูกต้อง!", "danger")
            return redirect(url_for("admin_panel"))

    # เช็คว่าล็อกอินค้างไว้หรือยัง
    is_admin = session.get("is_admin", False)
    rows = []
    
    if is_admin:
        try:
            response = supabase.table("payments").select("*").order("id", desc=True).execute()
            rows = response.data
        except Exception as e:
            print(f"Error fetching data: {e}")

    return render_template("admin.html", payments=rows, is_admin=is_admin)


# --- ล็อกเอาต์ออกจากระบบแอดมิน ---
@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("🔒 ออกจากระบบแอดมินเรียบร้อยแล้ว", "success")
    return redirect(url_for("index"))


# --- ฟังก์ชันสำหรับแอดมินกดลบข้อมูล (ล็อกให้ลบได้เฉพาะแอดมิน) ---
@app.route("/delete/<int:payment_id>/<filename>", methods=["POST"])
def delete_payment(payment_id, filename):
    # 🚨 ตรวจความปลอดภัย: ถ้าไม่ใช่แอดมินที่ล็อกอินอยู่ ห้ามลบเด็ดขาด!
    if not session.get("is_admin", False):
        flash("⛔ คุณไม่มีสิทธิ์ลบข้อมูลนี้", "danger")
        return redirect(url_for("index"))

    try:
        supabase.storage.from_(BUCKET_NAME).remove([filename])
        supabase.table("payments").delete().eq("id", payment_id).execute()
        flash("🗑️ ลบข้อมูลบนคลาวด์เรียบร้อยแล้ว", "success")
    except Exception as e:
        flash(f"ลบไม่สำเร็จ: {e}", "danger")

    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True)