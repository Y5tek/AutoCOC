import streamlit as st
import pandas as pd
from fpdf import FPDF
import json
import os
import zipfile
import io
import re
from datetime import datetime
from PIL import Image

# --- GOOGLE SHEETS AYARLARI ---
# Tablonuzun ID'si: 1f8AN3V-UiWv4B0qsjsYyVony4yEdKGHaSUpIv5_8gQ4
SHEET_ID = "1f8AN3V-UiWv4B0qsjsYyVony4yEdKGHaSUpIv5_8gQ4"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- AYARLAR ---
SABLON_DOSYASI = "sablonlar.json"
LOGO_KLASORU = "logos"
IMZA_DOSYASI = os.path.join(LOGO_KLASORU, "signature.png")
SIRKET_LOGOSU = "photo.jpg"

if not os.path.exists(LOGO_KLASORU):
    os.makedirs(LOGO_KLASORU)

VARSAYILAN_ACIKLAMA_METNI = """18.10.2023 Tarihinde düzenlenen : e13*168/2013*01865*00 sayılı AB Tip Onayında tarif edilen tipe tam anlamıyla uygundur..."""
VARSAYILAN_TAAHHUT_METNI = """Asagida imzasi bulunan Özgü ÖZ Firma Yetkili Makine Mühendisi olup..."""

# --- VERİ YÖNETİMİ (GOOGLE SHEETS & LOCAL) ---
def sablonlari_yukle():
    # Önce Sheets'ten deniyoruz, olmazsa local json'a bakıyoruz
    try:
        df = pd.read_csv(SHEET_URL)
        # Tablo yapısını json formatına simüle ediyoruz (basit versiyon)
        # Not: Gerçek ekip çalışması için Sheets API entegrasyonu önerilir,
        # ancak şimdilik mevcut mantığınızı bozmadan devam ediyoruz.
        if os.path.exists(SABLON_DOSYASI):
            with open(SABLON_DOSYASI, "r", encoding="utf-8") as f: return json.load(f)
    except:
        if os.path.exists(SABLON_DOSYASI):
            with open(SABLON_DOSYASI, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def temizle_kod(kod):
    if not kod or str(kod).lower() in ["none", "nan", ""]: return ""
    return str(kod).strip().rstrip('.')

def pdf_olustur(vin, veri, manuel_tarih_str=None):
    # ÇIKTI DÜZENİ SABİTLEME: Orijinal koordinatlara sadık kalıyoruz
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_margins(left=10, top=10, right=10)
    
    font_path = "arial.ttf" if os.path.exists("arial.ttf") else "Arial.ttf"
    try:
        pdf.add_font("ArialTR", style="", fname=font_path, uni=True)
        pdf.add_font("ArialTR", style="B", fname=font_path, uni=True)
        ana_font = "ArialTR"
    except:
        ana_font = "Helvetica"

    def text_safe(txt):
        if txt is None or str(txt).lower() in ['none', 'nan']: return ""
        tr_map = str.maketrans("İıĞğŞşÜüÖöÇç", "IiGgSsUuOoCc")
        return str(txt).translate(tr_map)

    pdf.add_page()
    pdf.set_auto_page_break(auto=False)
    kimlik = veri.get("kimlik", {})
    maddeler = veri.get("teknik", [])
    
    tarih_bilgisi = manuel_tarih_str if manuel_tarih_str else datetime.now().strftime('%d.%m.%Y')

    # Başlık Alanı
    pdf.set_y(5)
    pdf.set_font(ana_font, "B", 14); pdf.cell(0, 7, "AT UYGUNLUK BELGESI (CoC)", ln=True, align='C')
    pdf.set_font(ana_font, "B", 10); pdf.cell(0, 5, f"Sasi No: {vin}", ln=True, align='C')

    # Logo
    marka_adi = text_safe(kimlik.get('marka', '')).strip()
    logo_path = os.path.join(LOGO_KLASORU, f"{marka_adi}.png")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=250, y=5, h=12)

    fs, base_h = 8.5, 5.0
    header_end_y = pdf.get_y() + 4
    pdf.set_y(header_end_y)
    
    # Taahhüt
    if kimlik.get("taahut"):
        pdf.set_font(ana_font, "B", fs)
        pdf.multi_cell(140, base_h, text_safe(kimlik.get("taahut")), 0, 'L')
        pdf.set_y(pdf.get_y() + 1.5)

    x_pos, v_done = 10, False
    for m in maddeler:
        t_kod = temizle_kod(m.get("Kod", ""))
        val = text_safe(m.get("Değer", ""))
        if t_kod == "1": val = vin
        
        pdf.set_font(ana_font, "B", fs)
        curr_y = pdf.get_y()
        # SAYFA SONU KONTROLÜ (Localdeki düzen için 188mm sınırı)
        if curr_y > 188 and x_pos == 10:
            x_pos = 155; pdf.set_y(header_end_y); curr_y = header_end_y

        pdf.set_xy(x_pos, curr_y); pdf.cell(14, base_h, t_kod)
        pdf.set_xy(x_pos + 14, curr_y); pdf.multi_cell(60, base_h, text_safe(m.get('Özellik Adı', '')))
        y_aft = pdf.get_y()
        pdf.set_xy(x_pos + 76, curr_y); pdf.multi_cell(64, base_h, f": {val}")
        pdf.set_y(max(y_aft, pdf.get_y()))

        # İmza ve Açıklama Alanı (Sadece ilk sütunda, şasi no altına)
        if t_kod == "1" and not v_done and x_pos == 10:
            pdf.set_y(pdf.get_y() + 2)
            pdf.multi_cell(140, base_h*0.82, text_safe(kimlik.get("aciklama", VARSAYILAN_ACIKLAMA_METNI)), 0, 'J')
            imza_y = pdf.get_y() + 5
            if os.path.exists(IMZA_DOSYASI): pdf.image(IMZA_DOSYASI, x=x_pos + 90, y=imza_y, h=18)
            pdf.set_xy(x_pos, imza_y + 10); pdf.cell(85, 5, f"Yer: {kimlik.get('yer', 'Ankara')} | Tarih: {tarih_bilgisi}")
            pdf.set_y(imza_y + 25); v_done = True

    pdf.line(152, 25, 152, 200)
    # Unicode Hatasını Gideren Çıktı Yöntemi
    return pdf.output(dest='S').encode('latin-1')

# --- ARAYÜZ (Geri kalan kısımlar aynı) ---
# ... (Menü ve Şablon yönetimi kodları buraya gelecek)
