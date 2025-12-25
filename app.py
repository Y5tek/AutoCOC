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

# --- YARDIMCI FONKSİYONLAR ---
def sablonlari_yukle():
    if not os.path.exists(SABLON_DOSYASI): return {}
    try:
        with open(SABLON_DOSYASI, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def temizle_kod(kod):
    if not kod or str(kod).lower() in ["none", "nan", ""]: return ""
    return str(kod).strip().rstrip('.')

def yeni_versiyon_adi_bul(temel_ad):
    mevcut = sablonlari_yukle().keys()
    temiz_ad = re.sub(r'_v\d+$', '', temel_ad)
    versiyon = 1
    yeni_ad = f"{temiz_ad}_v{versiyon}"
    while yeni_ad in mevcut:
        versiyon += 1
        yeni_ad = f"{temiz_ad}_v{versiyon}"
    return yeni_ad

def sablon_kaydet(isim, kimlik_verisi, teknik_df):
    mevcut = sablonlari_yukle()
    mevcut[isim] = {"kimlik": kimlik_verisi, "teknik": teknik_df.to_dict(orient="records")}
    with open(SABLON_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(mevcut, f, ensure_ascii=False, indent=4)

def sablon_sil(isim):
    mevcut = sablonlari_yukle()
    if isim in mevcut:
        del mevcut[isim]
        with open(SABLON_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(mevcut, f, ensure_ascii=False, indent=4)
        return True
    return False

# --- PDF MOTORU (LOCAL DÜZEN KİLİTLİ) ---
def pdf_olustur(vin, veri, manuel_tarih_str=None):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_margins(left=10, top=10, right=10)
    font_path = "arial.ttf" if os.path.exists("arial.ttf") else "Arial.ttf"
    try:
        pdf.add_font("ArialTR", style="", fname=font_path, uni=True)
        pdf.add_font("ArialTR", style="B", fname=font_path, uni=True)
        ana_font = "ArialTR"
    except: ana_font = "Helvetica"

    def text_safe(txt):
        if txt is None or str(txt).lower() in ['none', 'nan']: return ""
        tr_map = str.maketrans("İıĞğŞşÜüÖöÇç", "IiGgSsUuOoCc")
        return str(txt).translate(tr_map)

    pdf.add_page()
    pdf.set_auto_page_break(auto=False)
    kimlik = veri.get("kimlik", {})
    maddeler = veri.get("teknik", [])
    tarih_bilgisi = manuel_tarih_str if manuel_tarih_str else datetime.now().strftime('%d.%m.%Y')

    pdf.set_y(5)
    pdf.set_font(ana_font, "B", 14); pdf.cell(0, 7, "AT UYGUNLUK BELGESI (CoC)", ln=True, align='C')
    pdf.set_font(ana_font, "B", 10); pdf.cell(0, 5, f"Sasi No: {vin}", ln=True, align='C')

    marka_adi = text_safe(kimlik.get('marka', '')).strip()
    logo_path = os.path.join(LOGO_KLASORU, f"{marka_adi}.png")
    if os.path.exists(logo_path): pdf.image(logo_path, x=250, y=5, h=12)

    fs, base_h = 8.5, 5.0
    header_end_y = pdf.get_y() + 4
    pdf.set_y(header_end_y)
    
    if kimlik.get("taahut"):
        pdf.set_font(ana_font, "B", fs); pdf.multi_cell(140, base_h, text_safe(kimlik.get("taahut")), 0, 'L')
        pdf.set_y(pdf.get_y() + 1.5)

    x_pos, v_done = 10, False
    for m in maddeler:
        t_kod = temizle_kod(m.get("Kod", ""))
        val = text_safe(m.get("Değer", ""))
        if t_kod == "1": val = vin
        pdf.set_font(ana_font, "B", fs)
        curr_y = pdf.get_y()
        if curr_y > 188 and x_pos == 10:
            x_pos = 155; pdf.set_y(header_end_y); curr_y = header_end_y

        pdf.set_xy(x_pos, curr_y); pdf.cell(14, base_h, t_kod)
        pdf.set_xy(x_pos + 14, curr_y); pdf.multi_cell(60, base_h, text_safe(m.get('Özellik Adı', '')))
        y_aft = pdf.get_y()
        pdf.set_xy(x_pos + 76, curr_y); pdf.multi_cell(64, base_h, f": {val}")
        pdf.set_y(max(y_aft, pdf.get_y()))

        if t_kod == "1" and not v_done and x_pos == 10:
            pdf.set_y(pdf.get_y() + 2)
            pdf.multi_cell(140, base_h*0.82, text_safe(kimlik.get("aciklama", VARSAYILAN_ACIKLAMA_METNI)), 0, 'J')
            imza_y = pdf.get_y() + 5
            if os.path.exists(IMZA_DOSYASI): pdf.image(IMZA_DOSYASI, x=x_pos + 90, y=imza_y, h=18)
            pdf.set_xy(x_pos, imza_y + 10); pdf.cell(85, 5, f"Yer: {kimlik.get('yer', 'Ankara')} | Tarih: {tarih_bilgisi}")
            pdf.set_y(imza_y + 25); v_done = True

    pdf.line(152, 25, 152, 200)
    return pdf.output(dest='S').encode('latin-1')

# --- ARAYÜZ ---
st.set_page_config(page_title="Vianext AutoCOC Pro", layout="wide")

if 'current_df' not in st.session_state: 
    st.session_state.current_df = pd.DataFrame(columns=["Sıra", "Kod", "Özellik Adı", "Değer"])

menu = st.sidebar.radio("Menü", ["🏠 Ana Sayfa", "🏭 Belge Üretimi", "📝 Şablon Yönetimi", "⚙️ Logo & İmza Ayarları"])

if menu == "🏠 Ana Sayfa":
    st.title("📊 AutoCOC Özet Gösterge Paneli")
    sablonlar = sablonlari_yukle()
    marka_datalar = {}
    for k, v in sablonlar.items():
        m_ad = v['kimlik'].get('marka', 'Bilinmeyen')
        marka_datalar[m_ad] = marka_datalar.get(m_ad, 0) + 1
    c1, c2 = st.columns(2)
    c1.metric("Toplam Marka", len(marka_datalar))
    c2.metric("Toplam Şablon", len(sablonlar))
    st.divider()
    if marka_datalar:
        g_cols = st.columns(4)
        for i, (m, s) in enumerate(marka_datalar.items()):
            with g_cols[i % 4]:
                st.write(f"**{m}** ({s} Şablon)")

elif menu == "📝 Şablon Yönetimi":
    st.header("🛠️ Şablon Yönetimi")
    tab1, tab2 = st.tabs(["📂 Düzenle", "🆕 Yeni"])
    with tab1:
        s_all = sablonlari_yukle()
        if s_all:
            search = st.text_input("🔍 Şablon Ara").lower()
            filtered = {k: v for k, v in s_all.items() if search in k.lower()}
            if filtered:
                s_sec = st.selectbox("Şablon Seç", list(filtered.keys()))
                if st.button("📂 Yükle"):
                    st.session_state.current_df = pd.DataFrame(s_all[s_sec]["teknik"])
                    st.session_state.marka = s_all[s_sec]["kimlik"].get("marka", "")
                    st.session_state.s_ad = yeni_versiyon_adi_bul(s_sec); st.rerun()

    with tab2:
        upl = st.file_uploader("Excel/CSV", type=["xlsx", "csv"])
        if upl:
            st.session_state.current_df = pd.read_excel(upl) if upl.name.endswith('.xlsx') else pd.read_csv(upl)
            st.success("Yüklendi!")

    st.divider()
    c_a, c_b = st.columns(2)
    s_ad = c_a.text_input("Şablon İsmi", value=st.session_state.get('s_ad', ''))
    marka = c_b.text_input("Marka Adı", value=st.session_state.get('marka', ''))
    final_df = st.data_editor(st.session_state.current_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Kaydet"):
        if s_ad and marka:
            sablon_kaydet(s_ad, {"marka": marka, "taahut": VARSAYILAN_TAAHHUT_METNI, "aciklama": VARSAYILAN_ACIKLAMA_METNI, "yer": "Ankara"}, final_df)
            st.success("Kaydedildi!"); st.rerun()

elif menu == "🏭 Belge Üretimi":
    st.header("🖨️ PDF Üretim Merkezi")
    sablonlar = sablonlari_yukle()
    if sablonlar:
        secim = st.selectbox("Şablon", list(sablonlar.keys()))
        tx = st.text_area("Şasiler (Alt alta)")
        if st.button("🚀 Üret") and tx:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for v in [x.strip() for x in tx.split('\n') if x.strip()]:
                    zf.writestr(f"{v}.pdf", pdf_olustur(v, sablonlar[secim]))
            st.download_button("📦 İndir", buf.getvalue(), "coc_paket.zip")

elif menu == "⚙️ Logo & İmza Ayarları":
    st.header("⚙️ Ayarlar")
    m_l = st.text_input("Marka Adı (Logo için)")
    lg = st.file_uploader("Logo (PNG)", type=["png"])
    if st.button("Kaydet") and lg and m_l:
        Image.open(lg).save(os.path.join(LOGO_KLASORU, f"{m_l.strip()}.png"), "PNG")
        st.success("Logo Kaydedildi")
