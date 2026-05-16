# -*- coding: utf-8 -*-
import os
import sys
import base64
import random
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, url_for, session
from supabase import create_client

app = Flask(__name__)
app.secret_key = "super_secret_key_for_flash_messages"

# 🔑 ตั้งรหัสผ่านสำหรับแอดมิน
ADMIN_PASSWORD = "01122004" 

# 👥 รายชื่อระบบ
ALLOWED_NAMES = [
    # รุ่น 14
    "เหมยเหมย", "วุ้นเป็ด", "กาฟิว", "ไฟท์", "กัน", "ต้นข้าว", "แอน", "น้ำมนต์", 
    "เนส", "จ๊ะจ๋า", "แพนเค้ก", "อาคลัง", "โอม", "เอ็มมี่", "กีตาร์", "หมูอ้วน", "อุ๋มอิ๋ม", "ปัญปัญ",
    
    # รุ่น 15
    "นุ่น", "จ้าว", "โฟร์", "ลูกไหม", "ออย", "ปอแก้ว", "เชอร์รี่", "สารวัตร", "ฟีฟ่า", 
    "มาร์ติน", "ปังปัง", "ฟลุ๊ก", "พีเจ", "ฟิล์ม", "เฟรม"
]

# --- 🔌 เชื่อมต่อ Supabase แบบมาตรฐาน (ลดความซับซ้อนของ Options เพื่อไม่ให้พังบน Linux) ---
SUPABASE_URL = "https://atnjjcdcaxuqbzzzhloy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0bmpqY2RjYXh1cWJ6enpobG95Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODkxMDUxMywiZXhwIjoyMDk0NDg2NTEzfQ.R97ZWVQUVel23O0ruF_t642YloTd_INNpFaxqEUitO8" 

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "payment-slips"  

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- หน้าแรก (ส่งฟอร์มสลิป) ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        amount = request.form.get("amount")
        file = request.files.get("slip")

        if not name or not amount or not file or file.filename == "":
            flash("❌ กรุณากรอกข้อมูลและแนบสลิปให้ครบถ้วน", "danger")
            return redirect(url_for("index"))

        if name not in ALLOWED_NAMES:
            flash("❌ ไม่พบชื่อของคุณในระบบ กรุณาตรวจสอบการพิมพ์สะกดคำ", "danger")
            return redirect(url_for("index"))

        if file and allowed_file(file.filename):
            file_ext = file.filename.rsplit(".", 1)[1].lower()
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_num = random.randint(1000, 9999)
            filename = f"slip_{current_time}_{random_num}.{file_ext}"

            try:
                # 1. อ่านไฟล์รูปออกมาเป็นก้อนข้อมูลดิบ (bytes)
                raw_data = file.read()
                
                # 2. ส่งข้อมูลดิบแบบ bytes เข้าไปตรงๆ และระบุฟอร์แมตไฟล์ใน Content-Type ให้ถูกต้องรูปจะได้ไม่ขึ้นตัวต่างดาว
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=filename,
                    file=raw_data,  # 👈 ส่งก้อน bytes สดๆ ปลอดภัยสุด ไม่พังเป็น BytesIO แน่นอน
                    file_options={"content-type": f"image/{file_ext if file_ext != 'jpg' else 'jpeg'}"},
                )
                
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)

                # 3. เข้ารหัสชื่อภาษาไทยป้องกัน ASCII error ระดับ Database
                encoded_name = base64.b64encode(name.encode('utf-8')).decode('utf-8')

                data = {
                    "name": encoded_name, 
                    "amount": float(amount),
                    "slip_url": public_url,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                supabase.table("payments").insert(data).execute()

                flash("🎉 อัปโหลดสลิปแจ้งชำระเงินสำเร็จแล้ว!", "success")
                return redirect(url_for("index"))

            except Exception as e:
                flash(f"เกิดข้อผิดพลาด: {str(e)}", "danger")
                return redirect(url_for("index"))
        else:
            flash("❌ รูปภาพต้องเป็นนามสกุล png, jpg, jpeg, gif เท่านั้น", "danger")
            return redirect(url_for("index"))

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

    is_admin = session.get("is_admin", False)
    rows = []
    total_amount = 0   # 👈 1. ประกาศตัวแปรตั้งต้น ยลื่นสีเหลืองจะหายไปทันที!
    total_count = 0    # 👈 2. ประกาศตัวแปรนับจำนวนรายการ
    
    if is_admin:
        try:
            response = supabase.table("payments").select("*").order("id", desc=True).execute()
            rows = response.data
            
            for row in rows:
                # ถอดรหัสชื่อกลับเป็นภาษาไทยเพื่อแสดงผลบนตารางแอดมิน
                try:
                    encoded_name = row.get("name", "")
                    row["name"] = base64.b64decode(encoded_name).decode('utf-8')
                except Exception:
                    pass
                
                # บวกสะสมยอดเงินเข้าตัวแปร
                total_amount += row.get("amount", 0)
            
            # นับจำนวนรายการทั้งหมดที่ดึงมาได้
            total_count = len(rows)
                    
        except Exception as e:
            print(f"Error fetching data: {e}")

    # ส่งตัวแปรทั้งหมดไปที่หน้า admin.html ธีมดาร์กสุดเท่ของเรา
    return render_template("admin.html", payments=rows, is_admin=is_admin, total_amount=total_amount, total_count=total_count)


# --- ล็อกเอาต์ออกจากระบบแอดมิน ---
@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("🔒 ออกจากระบบแอดมินเรียบร้อยแล้ว", "success")
    return redirect(url_for("index"))


# --- ฟังก์ชันสำหรับแอดมินกดลบข้อมูล ---
@app.route("/delete/<int:payment_id>/<filename>", methods=["POST"])
def delete_payment(payment_id, filename):
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