"""
sinif_planlama — Veri Güncelleme Scripti
=========================================
Kullanım: python3 guncelle.py
"""
import subprocess, sys, os
from pathlib import Path

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try: import gdown
except ImportError: print("📦 gdown kuruluyor..."); install("gdown"); import gdown

try: import openpyxl
except ImportError: print("📦 openpyxl kuruluyor..."); install("openpyxl"); import openpyxl

import json, re
from collections import defaultdict

# ── AYARLAR ──────────────────────────────────────────────────────────
SHEETS_ID  = "1RiAECKwP8w2KHBB0ZueygS6RchEqwvvnALaJCfuoUp4"
PROJE_DIR  = Path(__file__).parent
DB_PATH    = PROJE_DIR / "veritabani.json"
HTML_TMPL  = PROJE_DIR / "sinif_planlama_sablon.html"
HTML_OUT   = PROJE_DIR / "sinif_planlama.html"
XLSX_CACHE = PROJE_DIR / "_cache_sheets.xlsx"
# ─────────────────────────────────────────────────────────────────────

def indir():
    print("⬇️  Google Sheets indiriliyor...")
    url = f"https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=xlsx"
    gdown.download(url, str(XLSX_CACHE), quiet=False, fuzzy=True)
    kb = XLSX_CACHE.stat().st_size // 1024
    print(f"✅ İndirildi ({kb} KB)")
    return openpyxl.load_workbook(str(XLSX_CACHE), read_only=True, data_only=True)

def normalize(n):
    return re.sub(r'\s+',' ', str(n).strip().upper()
        .replace('İ','I').replace('Ğ','G').replace('Ş','S')
        .replace('Ü','U').replace('Ö','O').replace('Ç','C'))

def isle(wb):
    print("⚙️  Veriler işleniyor...")

    # Öğrenci listesi
    students = []
    for i, row in enumerate(wb['Ogrenci_Listesi'].iter_rows(values_only=True)):
        if i == 0 or all(v is None for v in row): continue
        if row[0] and row[1]:
            students.append({'id':int(float(row[0])),'name':str(row[1]).strip(),
                             'kurum':str(row[2]).strip(),'sube':str(row[3]).strip()})
    print(f"   👥 {len(students)} öğrenci")

    # Master veritabanı
    master = []
    for i, row in enumerate(wb['Master_Veritabani'].iter_rows(values_only=True)):
        if i == 0 or all(v is None for v in row[:11]): continue
        try:
            oid = int(float(row[4])) if row[4] else None
            ders,durum,kaz = str(row[7]).strip(),str(row[8]).strip(),str(row[10]).strip()
            if oid and ders and kaz:
                master.append({'oid':oid,'ders':ders,'durum':durum,'kaz':kaz})
        except: pass
    print(f"   📊 {len(master)} sınav kaydı")

    # Form yanıtları
    ws = wb['Form_Yanitlari']
    form_cols, form_rows = [], []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if all(v is None for v in row): continue
        if i == 0: form_cols = [str(c).strip() if c else '' for c in row]; continue
        if row[1]: form_rows.append(row)
    form_kaz = [c for c in form_cols[3:] if c not in ('','E-posta Adresi','Puan')]

    student_map = {normalize(s['name']): s['id'] for s in students}
    manual_map  = {'AZRA YAZI':270,'TAYLAN GUNDOGAN':725,'ELIZABETH EVSEN':60,
                   'LAL SARIASLAN':573,'VAHIT KELES':743,'KUBRA KAYA':722,
                   'BIRCE BAYTAZ':575,'DEFNE DEMIRBAKAN':108}

    form_scores = {}
    for row in form_rows:
        fname = str(row[1]).strip() if row[1] else ''
        norm  = normalize(fname)
        oid   = student_map.get(norm)
        if not oid:
            for k,v in manual_map.items():
                if k in norm: oid=v; break
        if not oid: continue
        scores = {}
        for j, kname in enumerate(form_kaz):
            try: scores[kname] = int(row[j+3])
            except: pass
        form_scores[oid] = scores
    print(f"   📝 {len(form_scores)} form yanıtı eşleşti")

    # Hata haritası
    ogr_hatalar = defaultdict(lambda: defaultdict(lambda: {'y':0,'b':0}))
    for r in master:
        key = f"{r['ders']}|||{r['kaz']}"
        ogr_hatalar[r['oid']][key]['y' if r['durum']=='Yanlış' else 'b'] += 1

    # Kazanım listesi
    kaz_set = defaultdict(lambda: {'ders':'','yanlis':set(),'bos':set()})
    for r in master:
        key = (r['ders'], r['kaz'])
        kaz_set[key]['ders'] = r['ders']
        if r['durum'] == 'Yanlış': kaz_set[key]['yanlis'].add(r['oid'])
        elif r['durum'] == 'Boş':  kaz_set[key]['bos'].add(r['oid'])

    kazanim_list = []
    for (ders, kaz), st in kaz_set.items():
        if not st['yanlis'] and not st['bos']: continue
        key_str = f"{ders}|||{kaz}"
        detail  = []
        for oid, hd in ogr_hatalar.items():
            if key_str in hd:
                y,b = hd[key_str]['y'], hd[key_str]['b']
                if y > 0 or b > 0: detail.append({'id':int(oid),'y':y,'b':b})
        detail.sort(key=lambda x: -(x['y']*3+x['b']))
        kazanim_list.append({'ders':ders,'kaz':kaz,
            'yanlis_ids':[d['id'] for d in detail if d['y']>0],
            'bos_ids':   [d['id'] for d in detail if d['b']>0],
            'detail':    detail})
    print(f"   🎯 {len(kazanim_list)} kazanım")

    return {
        'students':        students,
        'kazanim_list':    kazanim_list,
        'ogrenci_hatalar': {str(k):{kk:vv for kk,vv in v.items()} for k,v in ogr_hatalar.items()},
        'form_scores':     {str(k):v for k,v in form_scores.items()},
        'meta': {'total_master':len(master),'total_kazanim':len(kazanim_list),'form_matched':len(form_scores)}
    }

def kaydet(db):
    with open(DB_PATH,'w',encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, separators=(',',':'))
    print(f"✅ veritabani.json güncellendi ({DB_PATH.stat().st_size//1024} KB)")

def html_guncelle(db):
    if not HTML_TMPL.exists():
        print(f"⚠️  {HTML_TMPL.name} bulunamadı, HTML güncellenmedi.")
        return
    with open(HTML_TMPL, encoding='utf-8') as f: tmpl = f.read()
    html = tmpl.replace('__EMBEDDED_DB__', json.dumps(db, ensure_ascii=False, separators=(',',':')))
    with open(HTML_OUT,'w',encoding='utf-8') as f: f.write(html)
    print(f"✅ sinif_planlama.html güncellendi ({HTML_OUT.stat().st_size//1024} KB)")

def git_push():
    print("\n📤 GitHub'a gönderiliyor...")
    os.chdir(PROJE_DIR)
    cmds = [
        ['git', 'add', 'veritabani.json', 'sinif_planlama.html'],
        ['git', 'commit', '-m', '🔄 Veri güncellendi'],
        ['git', 'push']
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # commit'te "nothing to commit" normal
            if 'nothing to commit' in result.stdout or 'nothing to commit' in result.stderr:
                print("ℹ️  Değişiklik yok, push atlandı.")
                return
            print(f"⚠️  {' '.join(cmd)} hatası:\n{result.stderr}")
            return
    print("✅ GitHub'a gönderildi! Site 1-2 dakika içinde güncellenir.")

if __name__ == '__main__':
    print("=" * 50)
    print("  Sınıf Planlama — Veri Güncelleme")
    print("=" * 50)
    wb = indir()
    db = isle(wb)
    kaydet(db)
    html_guncelle(db)
    git_push()
    print()
    print("🎉 Tamamlandı!")
    print(f"   🌐 https://furkanceylan1.github.io/sinif-planlama/sinif_planlama.html")
