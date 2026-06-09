"""
dynamic_storage_batch.py
========================
Batch-Based Dynamic Storage Location Assignment

Nasıl çalışır:
  - DEPSO çalışır → final_batches oluşur
  - Aynı batch'te birlikte görünen ürün çiftleri tespit edilir
  - Bu çiftler birbirine yakın raflara taşınır
  - Lokal optimuma sıkışmamak için:
      * Her periyotta max %20 ürün taşınır
      * Taşıma kararına rastgelelik eklenir (exploration_rate)
      * Sadece yeterince sık birlikte görünen çiftler taşınır (min_cooccurrence)

Kullanım:
    cd src/
    python dynamic_storage_batch.py
"""

import utils
import random
import math
import time
import csv
import os
import matplotlib.pyplot as plt
from collections import defaultdict


# ==========================================
# ITEM CLASS
# ==========================================
class Item:
    def __init__(self, item_id, location_index):
        self.id = item_id
        self.location_index = location_index


# ==========================================
# BATCH CO-OCCURRENCE TRACKER
# ==========================================
def build_cooccurrence_matrix(final_batches):
    """
    DEPSO'nun ürettiği final_batches'e bakarak
    hangi ürün çiftlerinin aynı batch'te kaç kez
    birlikte göründüğünü sayar.

    Returns: {(item_id_1, item_id_2): count}
    """
    cooccurrence = defaultdict(int)
    for batch in final_batches:
        item_ids = []
        for order in batch:
            for item, _ in order.lines:
                if item.id not in item_ids:
                    item_ids.append(item.id)
        # Tüm çiftleri say
        for i in range(len(item_ids)):
            for j in range(i + 1, len(item_ids)):
                key = tuple(sorted([item_ids[i], item_ids[j]]))
                cooccurrence[key] += 1
    return cooccurrence


def update_cooccurrence(historical_cooccurrence, new_batches):
    """
    Birikimli co-occurrence matrisini günceller.
    Periyotlar boyunca birlikte görülen çiftler birikir.
    """
    new = build_cooccurrence_matrix(new_batches)
    for key, count in new.items():
        historical_cooccurrence[key] += count
    return historical_cooccurrence


# ==========================================
# BATCH-BASED RELOCATION
# ==========================================
def batch_based_relocate(items, item_id_map, cooccurrence,
                          locations_cache,
                          max_relocate_pct=0.20,
                          min_cooccurrence=2,
                          exploration_rate=0.15):
    """
    Batch co-occurrence'a göre ürünleri yeniden konumlandırır.

    Mantık:
    1. Sık birlikte batch'lenen çiftleri bul (min_cooccurrence eşiği)
    2. Bu çiftleri birbirine yakın raflara taşı
    3. Max %20 ürün taşı — büyük sarsıntı olmasın
    4. exploration_rate kadar rastgele taşıma ekle — lokal optimuma sıkışma

    Returns:
        reloc_count: kaç ürün taşındı
        avg_dist_before: taşıma öncesi ortalama batch içi mesafe
        avg_dist_after:  taşıma sonrası ortalama batch içi mesafe
    """
    if not cooccurrence:
        return 0, 0, 0

    # Max taşınabilecek ürün sayısı
    max_relocate = max(1, int(len(items) * max_relocate_pct))

    # Sık birlikte görünen çiftleri frekansa göre sırala
    strong_pairs = [(pair, cnt) for pair, cnt in cooccurrence.items()
                    if cnt >= min_cooccurrence]
    strong_pairs.sort(key=lambda x: x[1], reverse=True)

    if not strong_pairs:
        return 0, 0, 0

    # Taşınacak ürünleri belirle
    items_to_move = set()
    pair_targets = {}  # item_id → hedef item_id (yanına taşınacağı)

    for (id1, id2), cnt in strong_pairs:
        if len(items_to_move) >= max_relocate:
            break
        if id1 in item_id_map and id2 in item_id_map:
            items_to_move.add(id1)
            items_to_move.add(id2)
            pair_targets[id1] = id2  # id1, id2'nin yanına gidecek

    # Exploration: rastgele ek ürünler taşı (lokal optimuma sıkışmayı engelle)
    all_ids = list(item_id_map.keys())
    extra_count = max(1, int(len(items_to_move) * exploration_rate))
    for _ in range(extra_count):
        if len(items_to_move) < max_relocate:
            random_id = random.choice(all_ids)
            items_to_move.add(random_id)

    # Taşıma öncesi ortalama batch içi mesafe
    def avg_pair_dist(pairs_list, item_id_map):
        if not pairs_list:
            return 0
        total = 0
        count = 0
        for (id1, id2), _ in pairs_list[:50]:  # ilk 50 çift yeterli
            if id1 in item_id_map and id2 in item_id_map:
                loc1 = item_id_map[id1].location_index
                loc2 = item_id_map[id2].location_index
                total += float(utils.dist_matrix[loc1][loc2])
                count += 1
        return total / count if count > 0 else 0

    dist_before = avg_pair_dist(strong_pairs, item_id_map)

    # Taşıma işlemi
    reloc_count = 0
    for item_id in items_to_move:
        if item_id not in item_id_map:
            continue
        item = item_id_map[item_id]

        if item_id in pair_targets:
            target_id = pair_targets[item_id]
            if target_id in item_id_map:
                target_item = item_id_map[target_id]
                target_loc  = target_item.location_index
                target_loc_obj = utils.locations_cache[target_loc]

                # Hedef ürünün bulunduğu koridor ve yakın raflara bak
                target_aisle = target_loc_obj.aisle_id
                target_rack  = target_loc_obj.rack_pos

                # Aynı koridorda ±5 raf içinde boş lokasyon ara
                best_loc = None
                best_dist = float('inf')

                for rack_offset in range(1, 6):
                    for sign in [1, -1]:
                        new_rack = target_rack + sign * rack_offset
                        if 0 <= new_rack < 90:
                            # Bu lokasyon indexini bul
                            for side in range(2):
                                for slot in range(4):
                                    candidate_idx = (1 + target_aisle * 720
                                                     + side * 360
                                                     + new_rack * 4 + slot)
                                    if (1 <= candidate_idx < len(utils.locations_cache)
                                            and candidate_idx != item.location_index):
                                        d = float(utils.dist_matrix[
                                            item.location_index][candidate_idx])
                                        if d < best_dist:
                                            best_dist = d
                                            best_loc = candidate_idx

                if best_loc is not None and best_loc != item.location_index:
                    item.location_index = best_loc
                    reloc_count += 1
        else:
            # Exploration: rastgele yakın bir lokasyona taşı
            current_loc = item.location_index
            offset = random.randint(1, 10)
            new_idx = max(1, min(len(utils.locations_cache) - 1,
                                  current_loc + offset))
            if new_idx != current_loc:
                item.location_index = new_idx
                reloc_count += 1

    dist_after = avg_pair_dist(strong_pairs, item_id_map)
    return reloc_count, dist_before, dist_after


# ==========================================
# DEPSO RUNNER
# ==========================================
def run_depso_get_batches(orders):
    """DEPSO çalıştırır, mesafe + final_batches döndürür."""
    utils.route_cache.clear()
    final_batches, _, d, _ = utils.run_depso(
        orders=orders,
        num_particles=8,
        max_iterations=500,
        threshold_gbest=0.5,
        max_ls_iter=100,
        max_stagnation=20,
        v_p=0.5
    )
    return int(d), final_batches


# ==========================================
# MAIN DEMO
# ==========================================
def run_batch_dynamic_storage(num_orders=100, max_ol=6, max_parts_ol=6,
                               num_periods=5, period_size=20, seed=42,
                               max_relocate_pct=0.20,
                               min_cooccurrence=2,
                               exploration_rate=0.15):
    print("=" * 65)
    print("BATCH-BASED DYNAMIC STORAGE LOCATION ASSIGNMENT")
    print(f"Scenario: {num_orders}_{max_ol}_{max_parts_ol}")
    print(f"Periods: {num_periods}  |  Orders/period: {period_size}")
    print(f"Max relocate: {max_relocate_pct*100:.0f}%  |  "
          f"Min co-occ: {min_cooccurrence}  |  "
          f"Exploration: {exploration_rate*100:.0f}%")
    print("=" * 65)

    # Warehouse setup
    utils.set_seed(seed)
    locations = [utils.Location(index=0, aisle_id=0, rack_pos=0, side=1, slot=0)]
    idx = 1
    for aisle in range(10):
        for side in range(2):
            for rack in range(90):
                for slot in range(4):
                    locations.append(utils.Location(
                        index=idx, aisle_id=aisle,
                        rack_pos=rack, side=side, slot=slot))
                    idx += 1
    utils.create_distance_matrix(locations)

    # Items
    utils.item_weights.clear()
    items = []
    item_id_map = {}
    for i in range(1, 6001):
        item = Item(item_id=f"I_{i}", location_index=i)
        items.append(item)
        item_id_map[item.id] = item
        utils.item_weights[item.id] = random.uniform(0.1, 1.0)

    # Pareto
    c = math.log10(0.6) / math.log10(0.2)
    n_item = len(items)
    cp = [(y / n_item) ** c for y in range(1, n_item + 1)]
    sel_w = [cp[0]] + [cp[i] - cp[i-1] for i in range(1, len(cp))]

    def generate_orders(n, seed_offset):
        utils.set_seed(seed + seed_offset * 1000)
        orders = []
        for k in range(n):
            nl = random.randint(1, max_ol)
            us = set()
            while len(us) < nl:
                needed = nl - len(us)
                for itm in random.choices(items, weights=sel_w, k=needed*2):
                    us.add(itm)
                    if len(us) == nl:
                        break
            orders.append(utils.Order(
                order_id=f"P{seed_offset}_O{k}",
                lines=[(itm, random.randint(1, max_parts_ol))
                       for itm in list(us)]
            ))
        return orders

    # Birikimli co-occurrence matrisi
    historical_cooccurrence = defaultdict(int)
    results = []

    for period in range(1, num_periods + 1):
        print(f"\n--- Period {period}/{num_periods} ---")

        period_orders = generate_orders(period_size, seed_offset=period)

        # ADIM 1: Mevcut lokasyonlarla DEPSO
        d_before, final_batches = run_depso_get_batches(period_orders)
        print(f"  DEPSO (before): {d_before} LU  |  "
              f"Batches: {len(final_batches)}")

        # ADIM 2: Co-occurrence güncelle
        historical_cooccurrence = update_cooccurrence(
            historical_cooccurrence, final_batches)
        top_pairs = sorted(historical_cooccurrence.items(),
                           key=lambda x: x[1], reverse=True)[:5]
        print(f"  Top co-occ pairs: "
              f"{[(p[0][:6]+'..', p[1]) for p, c in top_pairs[:3]]}")

        # ADIM 3: Batch bazlı relokasyon
        reloc_count, dist_pair_before, dist_pair_after = batch_based_relocate(
            items=items,
            item_id_map=item_id_map,
            cooccurrence=historical_cooccurrence,
            locations_cache=utils.locations_cache,
            max_relocate_pct=max_relocate_pct,
            min_cooccurrence=min_cooccurrence,
            exploration_rate=exploration_rate
        )
        pair_impr = ((dist_pair_before - dist_pair_after) / dist_pair_before * 100
                     if dist_pair_before > 0 else 0)
        print(f"  ↻ Relocated: {reloc_count} items  |  "
              f"Avg pair dist: {dist_pair_before:.1f} → "
              f"{dist_pair_after:.1f} LU ({pair_impr:.1f}% closer)")

        # ADIM 4: YENİ lokasyonlarla AYNI siparişlerle DEPSO
        utils.route_cache.clear()
        d_after, _ = run_depso_get_batches(period_orders)
        diff     = d_after - d_before
        diff_pct = diff / d_before * 100 if d_before > 0 else 0
        verdict  = ("✓ Improved" if diff < -5
                    else ("~ Same" if abs(diff) <= 5 else "✗ Worse"))
        print(f"  DEPSO (after):  {d_after} LU  "
              f"({diff:+d} LU, {diff_pct:+.2f}%)  {verdict}")

        results.append({
            "Period":            period,
            "DEPSO_Before":      d_before,
            "DEPSO_After":       d_after,
            "Diff_LU":           diff,
            "Diff_%":            round(diff_pct, 2),
            "Relocations":       reloc_count,
            "PairDist_Before":   round(dist_pair_before, 2),
            "PairDist_After":    round(dist_pair_after, 2),
            "PairDist_Impr_%":   round(pair_impr, 2),
            "UniqueCooccPairs":  len(historical_cooccurrence),
        })

    # Özet
    print(f"\n{'='*65}")
    print("SUMMARY")
    print(f"{'='*65}")
    print(f"{'P':<3} {'Before':>8} {'After':>8} {'Diff':>7} "
          f"{'PairDist↓':>10} {'Result'}")
    print("-" * 55)
    for r in results:
        print(f"  {r['Period']:<2} {r['DEPSO_Before']:>8} "
              f"{r['DEPSO_After']:>8} {r['Diff_LU']:>+6} LU  "
              f"({r['PairDist_Impr_%']:>+5.1f}%)  "
              f"({r['Diff_%']:+.2f}%)")

    improved  = sum(1 for r in results if r['Diff_LU'] < 0)
    avg_diff  = sum(r['Diff_%'] for r in results) / len(results)
    print(f"\nPeriods improved: {improved}/{num_periods}")
    print(f"Average effect:   {avg_diff:+.2f}%")

    return results


# ==========================================
# CHART
# ==========================================
def plot_batch_dynamic(results, scenario_name="demo"):
    periods = [r['Period'] for r in results]
    before  = [r['DEPSO_Before'] for r in results]
    after   = [r['DEPSO_After']  for r in results]
    diffs   = [r['Diff_%']       for r in results]
    pair_d  = [r['PairDist_Impr_%'] for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        f'Batch-Based Dynamic Storage Location Assignment\n'
        f'Scenario: {scenario_name}  |  Same orders: Before vs After',
        fontsize=12, fontweight='bold'
    )

    BLUE  = '#185FA5'
    GREEN = '#3B6D11'
    RED   = '#E24B4A'

    # Panel 1: Before vs After bar
    x = range(len(periods))
    w = 0.35
    axes[0].bar([i - w/2 for i in x], before, width=w,
                color=BLUE, alpha=0.85, label='Before relocation')
    axes[0].bar([i + w/2 for i in x], after, width=w,
                color=GREEN, alpha=0.85, label='After relocation')
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels([f'P{p}' for p in periods])
    axes[0].set_ylabel('Travel Distance (LU)')
    axes[0].set_title('DEPSO: Before vs After\n(Same order set)', fontweight='bold')
    axes[0].legend()
    axes[0].grid(axis='y', alpha=0.3)

    # Panel 2: % improvement
    colors = [GREEN if d < 0 else RED for d in diffs]
    axes[1].bar(periods, diffs, color=colors, alpha=0.85, edgecolor='white')
    axes[1].axhline(0, color='black', lw=1)
    axes[1].set_xlabel('Period')
    axes[1].set_ylabel('DEPSO Distance Change (%)')
    axes[1].set_title('Relocation Effect on DEPSO\n(Green=improved)', fontweight='bold')
    axes[1].grid(axis='y', alpha=0.3)
    axes[1].set_xticks(periods)

    # Panel 3: Pair distance improvement
    axes[2].bar(periods, pair_d, color=BLUE, alpha=0.85, edgecolor='white')
    axes[2].axhline(0, color='black', lw=1)
    axes[2].set_xlabel('Period')
    axes[2].set_ylabel('Avg Co-Batch Pair Distance (%)')
    axes[2].set_title('Batch Pair Proximity Improvement\n(Higher = pairs moved closer)',
                       fontweight='bold')
    axes[2].grid(axis='y', alpha=0.3)
    axes[2].set_xticks(periods)

    avg = sum(diffs) / len(diffs)
    fig.text(0.5, -0.02,
             f'Avg DEPSO improvement: {avg:+.2f}%  |  '
             f'Periods improved: {sum(1 for d in diffs if d < 0)}/{len(diffs)}',
             ha='center', fontsize=10, fontweight='bold',
             color=GREEN if avg < 0 else RED)

    plt.tight_layout()
    fname = f'batch_dynamic_{scenario_name}.png'
    plt.savefig(fname, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"📊 Chart: {fname}")


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    os.makedirs("../data", exist_ok=True)

    test_scenarios = [
        (200, 6,  6, 5, 50, 42, "200_6_6"),   # büyük senaryo, 50 sipariş/periyot
        (200, 10, 6, 5, 50, 42, "200_10_6"),  # daha fazla batch
        (150, 6,  6, 5, 40, 42, "150_6_6"),
    ]

    summary = []
    for (num_orders, max_ol, max_parts_ol,
         num_periods, period_size, seed, label) in test_scenarios:
        print(f"\n{'#'*65}\n# SCENARIO: {label}\n{'#'*65}")

        results = run_batch_dynamic_storage(
            num_orders=num_orders, max_ol=max_ol,
            max_parts_ol=max_parts_ol,
            num_periods=num_periods, period_size=period_size,
            seed=seed,
            max_relocate_pct=0.20,
            min_cooccurrence=2,
            exploration_rate=0.15
        )

        plot_batch_dynamic(results, scenario_name=label)

        csv_path = f"../data/batch_dynamic_{label}.csv"
        fieldnames = ["Period","DEPSO_Before","DEPSO_After","Diff_LU",
                      "Diff_%","Relocations","PairDist_Before",
                      "PairDist_After","PairDist_Impr_%","UniqueCooccPairs"]
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()
            csv.DictWriter(f, fieldnames=fieldnames).writerows(results)

        avg  = sum(r['Diff_%'] for r in results) / len(results)
        impr = sum(1 for r in results if r['Diff_LU'] < 0)
        summary.append((label, avg, impr, len(results)))

    print(f"\n{'='*65}")
    print("FINAL SUMMARY — BATCH-BASED DYNAMIC STORAGE")
    print(f"{'='*65}")
    print(f"{'Scenario':<12} {'Avg Effect':>12} {'Improved':>10} {'Verdict'}")
    print("-" * 55)
    for label, avg, impr, total in summary:
        verdict = ("✓ Helps" if avg < -0.5
                   else ("~ Marginal" if avg < 0 else "✗ No benefit"))
        print(f"{label:<12} {avg:>+11.2f}%  {impr:>5}/{total:<5}  {verdict}")
