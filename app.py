import os
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, url_for
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "super_secret_key_for_flash_messages"

# --- 🔌 เชื่อมต่อ Supabase ---
# นำ URL และ API Key ที่ก๊อปปี้มาจากเว็บ Supabase มาใส่ตรงนี้ครับ
SUPABASE_URL = "https://atnjjcdcaxuqbzzzhloy.supabase.co"
SUPABASE_KEY = "sb_publishable_c52Jv74jtCh2FoDL3YvHhA_P435b2ZC"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "payment-slips"  # ชื่อ Bucket ที่เราสร้างไว้ใน Supabase Storage

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- หน้าแรก (ฟอร์มกรอกข้อมูล + ดึงข้อมูลจาก Supabase มาแสดง) ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        file = request.files.get("slip")

        if not name or not amount or not file or file.filename == "":
            flash("❌ กรุณากรอกข้อมูลและแนบสลิปให้ครบถ้วน", "danger")
            return redirect(url_for("index"))

        if file and allowed_file(file.filename):
            file_ext = file.filename.rsplit(".", 1)[1].lower()
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_name = name.replace(" ", "_")
            filename = f"{current_time}_{clean_name}.{file_ext}"

            try:
                # อ่านข้อมูลในไฟล์รูปภาพเพื่อเตรียมส่ง
                file_data = file.read()

                # 1. 📤 อัปโหลดไฟล์รูปภาพขึ้น Supabase Storage
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=filename,
                    file=file_data,
                    file_options={"content-type": file.content_type},
                )

                # 2. 🔗 ดึงลิงก์ URL สาธารณะของรูปภาพที่เพิ่งอัปโหลดไป
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(
                    filename
                )

                # 3. 📝 บันทึกข้อมูลรายชื่อและลิงก์รูปภาพลงฐานข้อมูลออนไลน์ (Table ชื่อ payments)
                data = {
                    "name": name,
                    "amount": float(amount),
                    "slip_url": public_url,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                supabase.table("payments").insert(data).execute()

                flash("🎉 อัปโหลดสลิปขึ้นระบบคลาวด์สำเร็จแล้ว!", "success")
                return redirect(url_for("index"))

            except Exception as e:
                flash(f"เกิดข้อผิดพลาด: {e}", "danger")
                return redirect(url_for("index"))
        else:
            flash("❌ รูปภาพต้องเป็นนามสกุล png, jpg, jpeg, gif เท่านั้น", "danger")
            return redirect(url_for("index"))

    # --- ดึงข้อมูลจาก Supabase มาแสดงบนตารางหน้าเว็บ ---
    try:
        response = (
            supabase.table("payments").select("*").order("id", desc=True).execute()
        )
        rows = response.data
    except Exception as e:
        print(f"Error fetching data: {e}")
        rows = []

    return render_template("index.html", payments=rows)


# --- ฟังก์ชันสำหรับกดลบข้อมูล ---
@app.route("/delete/<int:payment_id>/<filename>", methods=["POST"])
def delete_payment(payment_id, filename):
    try:
        # 1. ลบไฟล์สลิปใน Supabase Storage
        supabase.storage.from_(BUCKET_NAME).remove([filename])
        # 2. ลบแถวข้อมูลในตารางฐานข้อมูล
        supabase.table("payments").delete().eq("id", payment_id).execute()
        flash("🗑️ ลบข้อมูลบนคลาวด์เรียบร้อยแล้ว", "success")
    except Exception as e:
        flash(f"ลบไม่สำเร็จ: {e}", "danger")

    return redirect(url_for("index"))


# --- จัดย่อหน้าให้ถูกต้อง และเอา init_db() ออกเพื่อป้องกัน Error ---
if __name__ == "__main__":
    app.run(debug=True)