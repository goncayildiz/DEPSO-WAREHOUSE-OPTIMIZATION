import pandas as pd

# ==========================================================
# DEPSO_Full_35_Benchmark_With_Savings.csv → temizle ve sırala
# Kullanım: bu dosyayı data/ klasörüne koyun, sonra çalıştırın
# ==========================================================

input_file  = "../data/DEPSO_Full_35_Benchmark_With_Savings.csv"
output_file = "../data/DEPSO_Full_Benchmark_Cleaned_Final.csv"

try:
    df = pd.read_csv(input_file)

    print(f"✅ Dosya okundu: {len(df)} senaryo bulundu")

    # Eksik senaryo kontrolü
    expected = []
    for n in [50, 100, 150, 200]:
        for ol in [2, 6, 10]:
            for p in [2, 6, 10]:
                if not (n == 50 and ol == 2 and p == 2):  # makale 50_2_2 hariç
                    expected.append(f"{n}_{ol}_{p}")

    missing = [s for s in expected if s not in df['Scenario'].tolist()]
    extra   = [s for s in df['Scenario'].tolist() if s not in expected]

    if missing:
        print(f"⚠️  Eksik senaryolar: {missing}")
    else:
        print("✅ Tüm 35 senaryo mevcut, eksik yok")

    if extra:
        print(f"ℹ️  Beklenmeyen senaryolar: {extra}")

    # Mantıksal sıralama: Orders → MaxOL → MaxParts
    def sort_key(scenario):
        parts = scenario.split('_')
        return (int(parts[0]), int(parts[1]), int(parts[2]))

    df['_sort'] = df['Scenario'].apply(sort_key)
    df = df.sort_values('_sort').drop(columns=['_sort']).reset_index(drop=True)

    # Kaydet
    df.to_csv(output_file, index=False)
    print(f"\n✅ Temizlenmiş ve sıralanmış dosya kaydedildi: {output_file}")

    # Özet kontrol
    print("\n📊 İlk 5 senaryo:")
    print(df.head(5)[['Scenario', 'DEPSO_Avg', 'SOP_Avg', 'Gap_SOP_%']].to_string(index=False))

    print("\n📊 Son 5 senaryo (200'lük grup):")
    print(df.tail(5)[['Scenario', 'DEPSO_Avg', 'SOP_Avg', 'Gap_SOP_%']].to_string(index=False))

    print(f"\n📈 Genel Özet:")
    print(f"   Ort. DEPSO vs SOP    : {df['Gap_SOP_%'].mean():.2f}%")
    print(f"   Ort. DEPSO vs FCFS   : {df['Gap_FCFS_%'].mean():.2f}%")
    print(f"   Ort. DEPSO vs Savings: {df['Gap_Savings_%'].mean():.2f}%")

except FileNotFoundError:
    print(f"❌ Dosya bulunamadı: {input_file}")
    print("   CSV dosyasının data/ klasöründe olduğundan emin olun.")
except Exception as e:
    print(f"❌ Hata: {e}")