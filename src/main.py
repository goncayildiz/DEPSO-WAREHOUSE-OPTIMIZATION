import utils
import random
import math
import time
import csv
import os
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count

# ==========================================
# 1. DUMMY ITEM CLASS FOR TESTING
# ==========================================
class Item:
    def __init__(self, item_id, location_index):
        self.id = item_id
        self.location_index = location_index


warehouse_initialized = False


# ==========================================
# 2. BENCHMARK GENERATOR
# ==========================================
def generate_test_instance(num_orders, max_ol, max_parts_ol, seed=None):
    global warehouse_initialized

    if seed is not None:
        utils.set_seed(seed)

    # Warehouse layout sadece 1 kez oluşturulur
    if not warehouse_initialized:
        locations = [utils.Location(index=0, aisle_id=0, rack_pos=0, side=1, slot=0)]

        idx = 1
        for aisle in range(10):
            for side in range(2):
                for rack in range(90):
                    for slot in range(4):
                        locations.append(
                            utils.Location(
                                index=idx,
                                aisle_id=aisle,
                                rack_pos=rack,
                                side=side,
                                slot=slot
                            )
                        )
                        idx += 1

        utils.create_distance_matrix(locations)
        warehouse_initialized = True

    # Önceki senaryoların weight kalıntılarını temizle
    utils.item_weights.clear()

    # 6000 item üret
    items = []

    for i in range(1, 6001):
        item = Item(item_id=f"I_{i}", location_index=i)

        items.append(item)

        utils.item_weights[item.id] = random.uniform(0.1, 1.0)

    # Access frequency dağılımı
    c = math.log10(0.6) / math.log10(0.2)

    cumulative_probs = []

    n_item = len(items)

    for y_idx in range(1, n_item + 1):
        y_norm = y_idx / n_item
        cumulative_probs.append(y_norm ** c)

    selection_weights = [cumulative_probs[0]]

    for i in range(1, len(cumulative_probs)):
        selection_weights.append(
            cumulative_probs[i] - cumulative_probs[i - 1]
        )

    # Order generation
    orders = []

    for k in range(num_orders):

        num_lines = random.randint(1, max_ol)

        unique_selected = set()

        while len(unique_selected) < num_lines:
            # Kaç tane eksik elemanımız kaldığını hesaplıyoruz           
            needed = num_lines - len(unique_selected)
            
            # Eksik miktarın 2 katı kadar elemanı TOPLUCA çekiyoruz          
            candidates = random.choices(
                items,
                weights=selection_weights,
                k=needed * 2
            )

            # Çekilen adayları benzersiz kümemize (set) ekliyoruz
            for itm in candidates:
                unique_selected.add(itm)
                # İstediğimiz sayıya ulaştığımız an döngüden çıkıyoruz
                if len(unique_selected) == num_lines:
                    break


        order_lines = []

        for itm in list(unique_selected):

            parts = random.randint(1, max_parts_ol)

            order_lines.append((itm, parts))

        orders.append(
            utils.Order(
                order_id=f"O_{k}",
                lines=order_lines
            )
        )

    return orders

# ==========================================
# 3. SINGLE INSTANCE WORKER (FOR MULTIPROCESSING) <-- KOMPLE YENİ EKLENEN BLOK
# ==========================================
def run_single_instance(args):
    num_orders, max_ol, max_parts_ol, instance_no = args
    
    # Her çekirdek kendi bağımsız veri setini üretir
    orders = generate_test_instance(num_orders, max_ol, max_parts_ol, seed=instance_no)

    # Baselines
    d_sop = utils.calculate_sop_distance(orders, utils.locations_cache)
    d_fcfs = utils.calculate_fcfs_distance(orders, utils.locations_cache)

    start_sav = time.time()
    d_savings = utils.calculate_savings_distance(orders, utils.locations_cache)
    sav_runtime = time.time() - start_sav

    # DEPSO - Parçacık sayısı makaleye uygun olarak 15'e çıkarıldı
    start_time = time.time()
    _, _, d_depso, conv = utils.run_depso(
        orders=orders,
        num_particles=8,  # <-- 5 olan değer 15 yapıldı 🚀
        max_iterations=500,
        threshold_gbest=0.5,
        max_ls_iter=100,
        max_stagnation=20,
        v_p=0.5
    )
    runtime = time.time() - start_time

    return d_depso, d_sop, d_fcfs, d_savings, runtime, conv


# ==========================================
# 3.2 MULTI-RUN BENCHMARK EXECUTOR
# ==========================================

def run_benchmark_scenario(num_orders, max_ol, max_parts_ol, num_instances=10):

    scenario_name = f"{num_orders}_{max_ol}_{max_parts_ol}"

    print(f"\n{'=' * 75}")
    print(f"🔥 CURRENT SCENARIO: {scenario_name} | Target: {num_instances} Instances")
    print(f"{'=' * 75}")

    stats = {
        "depso": [],
        "sop": [],
        "fcfs": [],
        "savings": [],
        "time": []
    }

    last_convergence_curve = []

    # M2 Pro için paralel iş havuzu hazırlanıyor (Instance'lar paralel koşacak)
    worker_args = [(num_orders, max_ol, max_parts_ol, inst) for inst in range(1, num_instances + 1)]
    
    # Donanımı kilitlememek için çekirdek sayısının 2 eksiğini kullanıyoruz
    num_workers = max(3, num_instances) 
    
    with Pool(processes=num_workers) as pool:
        results = pool.map(run_single_instance, worker_args)

    # Sonuçları toplama ve ekrana yazdırma
    for instance_no, res in enumerate(results, 1):
        d_depso, d_sop, d_fcfs, d_savings, runtime, conv = res
        
        stats["depso"].append(d_depso)
        stats["sop"].append(d_sop)
        stats["fcfs"].append(d_fcfs)
        stats["savings"].append(d_savings)
        stats["time"].append(runtime)
        
        # En son instance'ın eğrisini grafik için sakla
        if instance_no == num_instances:
            last_convergence_curve = conv

        print(
            f"Instance {instance_no:02d}/{num_instances} | "
            f"DEPSO: {d_depso:.2f} | "
            f"SOP: {d_sop:.2f} | "
            f"FCFS: {d_fcfs:.2f} | "
            f"SAVINGS: {d_savings:.2f}  "
         )

    #  YENİ VE OVERFLOW ENGELLENMİŞ KISIM (YAPIŞTIRILACAK):
    avg_depso = sum(int(x) for x in stats["depso"]) / num_instances
    avg_sop = sum(int(x) for x in stats["sop"]) / num_instances
    avg_fcfs = sum(int(x) for x in stats["fcfs"]) / num_instances
    avg_savings = sum(int(x) for x in stats["savings"]) / num_instances
    avg_time = sum(stats["time"]) / num_instances

    # Improvement %
    gap_sop = ((avg_depso - avg_sop) / avg_sop) * 100
    gap_fcfs = ((avg_depso - avg_fcfs) / avg_fcfs) * 100
    gap_savings = ((avg_depso - avg_savings) / avg_savings) * 100

    # Convergence graph (optimized for memory leak)
    # Grafik çizimine başlamadan önce her ihtimale karşı eski kalıntıları temizliyoruz

    plt.clf()
    plt.close('all')

    # Figürü bir nesne değişkenine atayarak başlatıyoruz
    fig = plt.figure(figsize=(10, 6))
    plt.plot(
        last_convergence_curve,
        linewidth = 2
    )
    plt.title(f'Convergence - {scenario_name}')
    plt.xlabel('Iteration')
    plt.ylabel('Distance (LU)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(
        f"convergence_{scenario_name}.png",
        dpi=300
    )

    # İşimiz bittiğinde figür nesnesini ve Matplotlib'in RAM'deki tüm pencerelerini temizliyoruz
    plt.clf()
    plt.close(fig)
    plt.close('all')

    # Python'un çöp toplayıcısını (Garbage Collector) tetikleyerek RAM'i zorla boşaltıyoruz
    import gc
    gc.collect()

    # =========================================================================
    print(f"\n✅ Scenario Completed: {scenario_name}")

    print(f"DEPSO Avg : {avg_depso:.2f}")
    print(f"SOP Avg   : {avg_sop:.2f}")
    print(f"FCFS Avg  : {avg_fcfs:.2f}")
    print(f"SAVINGS Avg : {avg_savings:.2f}")
    print(f"Gap SOP   : {gap_sop:.2f}%")
    print(f"Gap FCFS  : {gap_fcfs:.2f}%")
    print(f"Gap SAVINGS : {gap_savings:.2f}%")
    print(f"Runtime   : {avg_time:.2f}s")

    return {
        "Scenario": scenario_name,
        "DEPSO_Avg": round(avg_depso, 2),
        "SOP_Avg": round(avg_sop, 2),
        "FCFS_Avg": round(avg_fcfs, 2),
        "Savings_Avg": round(avg_savings, 2),
        "Gap_SOP_%": round(gap_sop, 2),
        "Gap_FCFS_%": round(gap_fcfs, 2),
        "Gap_Savings_%": round(gap_savings, 2),
        "Runtime_Avg": round(avg_time, 2)
    }


# ==========================================
# 4. EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":

    # Veri klasörünün varlığı kontrol ediliyor
    os.makedirs("../data", exist_ok=True)
    csv_path = "../data/DEPSO_Full_35_Benchmark_With_Savings.csv"

    scenarios_to_test = [
        
        (50, 2, 6),
        (50, 6, 6),
        (50, 6, 2),
        (50, 10, 2),
        (50, 10, 6),
        (50, 2, 10),
        (50, 6, 10),
        (50, 10, 10),

        (100, 2, 2),
        (100, 2, 6),
        (100, 6, 2),
        (100, 6, 6),
        (100, 10, 2),
        (100, 10, 6),
        (100, 2, 10),
        (100, 6, 10),
        (100, 10, 10),

    
        (150, 2, 2),
        (150, 2, 6),
        (150, 6, 2),
        (150, 6, 6),
        (150, 10, 2),
        (150, 10, 6),
        (150, 2, 10),
        (150, 6, 10),
        (150, 10, 10),

        (200, 2, 2),
        (200, 2, 6),
        (200, 6, 2),
        (200, 6, 6),
        (200, 10, 2),
        (200, 10, 6),
        (200, 2, 10),
        (200, 6, 10),
        (200, 10, 10)     

            
    ]

    num_instances_per_scenario = 40

    # CSV Başlıklarını ilk açılışta bir kez yazıyoruz (Dosya sıfırlanır)
    fieldnames = ["Scenario", "DEPSO_Avg", "SOP_Avg", "FCFS_Avg", "Savings_Avg", "Gap_SOP_%", "Gap_FCFS_%", "Gap_Savings_%", "Runtime_Avg"]
    with open(csv_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    total_start = time.time()

    for i, s in enumerate(scenarios_to_test):
        print(f"\n[Scenario {i + 1}/{len(scenarios_to_test)}]")
        summary = run_benchmark_scenario(s[0], s[1], s[2], num_instances_per_scenario)

        # GÜVENLİ KAYIT: Her senaryo bittiğinde sadece o satırı dosyanın sonuna ekliyoruz (Append modu) 🚀
        with open(csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(summary)

    total_end = time.time()

    print(f"\n✅ ALL 35 BENCHMARK SCENARIOS COMPLETE!")
    print(f"⏱️ Total Execution Time: {(total_end - total_start) / 3600:.2f} hours")


