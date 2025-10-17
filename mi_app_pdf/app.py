from flask import Flask, request, send_file, render_template, redirect, url_for, session, flash
from datetime import datetime
from pathlib import Path
import pandas as pd
import zipfile
import io
import os

# Importa tu proceso
from procesos.tarjetas import run

app = Flask(__name__)
app.secret_key = "clave_super_segura"  # Cambia esto antes de subir

# ===========================
# 🔐 CONFIGURACIÓN
# ===========================
PASSWORD = os.getenv("APP_PASS", "1234segura")
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
LOGS_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = LOGS_DIR / "registros.csv"


# ===========================
# 🧩 FUNCIONES AUXILIARES
# ===========================
def registrar_uso(usuario, archivo, resultado):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo = pd.DataFrame([[ahora, usuario, archivo, resultado]],
                         columns=["Fecha", "Usuario", "Archivo", "Resultado"])
    if LOG_FILE.exists():
        df = pd.read_csv(LOG_FILE)
        df = pd.concat([df, nuevo], ignore_index=True)
    else:
        df = nuevo
    df.to_csv(LOG_FILE, index=False)


# ===========================
# 🔑 LOGIN
# ===========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        clave = request.form.get("password")
        if clave == PASSWORD:
            session["auth"] = True
            return redirect(url_for("index"))
        else:
            flash("❌ Clave incorrecta", "error")
    return render_template("login.html")


# ===========================
# 🏠 PÁGINA PRINCIPAL
# ===========================
@app.route("/index", methods=["GET", "POST"])
def index():
    if not session.get("auth"):
        return redirect(url_for("login"))

    if request.method == "POST":
        usuario = request.form.get("usuario")
        pdf = request.files["pdf"]

        if not pdf or not usuario:
            flash("⚠️ Debes indicar tu nombre y subir un PDF", "error")
            return redirect(url_for("index"))

        pdf_path = OUTPUT_DIR / pdf.filename
        pdf.save(pdf_path)

        out_folder = OUTPUT_DIR / "tarjetas"

        try:
            result = run(pdf_path, out_folder)

            # Crear ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
                csv_path = out_folder / "comprobantes_refinado" / "operaciones.csv"
                if csv_path.exists():
                    z.write(csv_path, arcname=csv_path.name)
                pdfs_folder = out_folder / "comprobantes_refinado" / "pdfs"
                if pdfs_folder.exists():
                    for pdf_file in pdfs_folder.glob("*.pdf"):
                        z.write(pdf_file, arcname=f"pdfs/{pdf_file.name}")
            zip_buffer.seek(0)

            registrar_uso(usuario, pdf.filename, "Éxito")

            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=f"resultados_{usuario}.zip",
                mimetype="application/zip"
            )

        except Exception as e:
            registrar_uso(usuario, pdf.filename, f"Error: {e}")
            flash(f"⚠️ Error procesando el PDF: {e}", "error")

    return render_template("index.html")


# ===========================
# 📊 REGISTROS
# ===========================
@app.route("/registros")
def registros():
    if not session.get("auth"):
        return redirect(url_for("login"))

    if LOG_FILE.exists():
        df = pd.read_csv(LOG_FILE)
        tabla = df.to_html(index=False, classes="table table-striped", border=0)
    else:
        tabla = "<p>No hay registros aún.</p>"

    return render_template("registros.html", tabla=tabla)


# ===========================
# 🚪 LOGOUT
# ===========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
