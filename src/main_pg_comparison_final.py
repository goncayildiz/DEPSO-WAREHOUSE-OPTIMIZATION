"""
main_pg_comparison_final.py
============================
DEPSO vs PG-DEPSO Final karşılaştırması.
35 senaryo × 40 instance.

Kullanım:
    cd src/
    caffeinate -i python main_pg_comparison_final.py
"""

import utils, random, math, time, csv, os, gc
from multiprocessing import Pool, cpu_count

class Item:
    def __init__(self, item_id, location_index):
        self.id = item_id
        self.location_index = location_index

warehouse_initialized = False

def generate_test_instance(num_orders, max_ol, max_parts_ol, seed=None):
    global warehouse_initialized
    if seed is not None:
        utils.set_seed(seed)
    if not warehouse_initialized:
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
        warehouse_initialized = True
    utils.item_weights.clear()
    items = []
    for i in range(1, 6001):
        item = Item(item_id=f"I_{i}", location_index=i)
        items.append(item)
        utils.item_weights[item.id] = random.uniform(0.1, 1.0)
    c = math.log10(0.6) / math.log10(0.2)
    cp = [(y/6000)**c for y in range(1, 6001)]
    sw = [cp[0]] + [cp[i]-cp[i-1] for i in range(1, len(cp))]
    orders = []
    for k in range(num_orders):
        nl = random.randint(1, max_ol)
        us = set()
        while len(us) < nl:
            for itm in random.choices(items, weights=sw, k=(nl-len(us))*2):
                us.add(itm)
                if len(us) == nl:
                    break
        orders.append(utils.Order(
            order_id=f"O_{k}",
            lines=[(itm, random.randint(1, max_parts_ol)) for itm in list(us)]
        ))
    return orders


def run_single_instance(args):
    num_orders, max_ol, max_parts_ol, inst = args
    orders = generate_test_instance(num_orders, max_ol, max_parts_ol, seed=inst)

    d_sop = utils.calculate_sop_distance(orders, utils.locations_cache)

    t0 = time.time()
    _, _, d_depso, _ = utils.run_depso(
        orders, 8, 500, 0.5, 100, 20, 0.5)
    rt_d = time.time() - t0

    t0 = time.time()
    _, _, d_pg, _ = utils.run_pg_depso_final(
        orders, 8, 500, 0.5, 100, 20, 0.5)
    rt_pg = time.time() - t0

    return int(d_depso), int(d_pg), int(d_sop), rt_d, rt_pg


def run_scenario(num_orders, max_ol, max_parts_ol, num_instances=40):
    scenario = f"{num_orders}_{max_ol}_{max_parts_ol}"
    print(f"\n{'='*65}\nScenario: {scenario}\n{'='*65}")

    args = [(num_orders, max_ol, max_parts_ol, i) for i in range(1, num_instances+1)]
    nw = max(3, min(num_instances, cpu_count()-2))

    with Pool(processes=nw) as pool:
        results = pool.map(run_single_instance, args)

    dep_v, pg_v, sop_v, rtd_v, rtpg_v = [], [], [], [], []
    for i, (d, pg, sop, rtd, rtpg) in enumerate(results, 1):
        dep_v.append(d); pg_v.append(pg); sop_v.append(sop)
        rtd_v.append(rtd); rtpg_v.append(rtpg)
        diff = (pg-d)/d*100 if d > 0 else 0
        print(f"  [{i:02d}] DEPSO={d}  PG={pg}  Diff={diff:+.1f}%  {'✓' if pg<=d else '✗'}")

    n = num_instances
    avg_d   = sum(float(x) for x in dep_v)  / n
    avg_pg  = sum(float(x) for x in pg_v)   / n
    avg_sop = sum(float(x) for x in sop_v)  / n

    gap_d   = (avg_d  - avg_sop) / avg_sop * 100
    gap_pg  = (avg_pg - avg_sop) / avg_sop * 100
    gap_pgd = (avg_pg - avg_d)   / avg_d   * 100

    wins_pg = sum(1 for d,pg in zip(dep_v,pg_v) if pg < d)
    wins_d  = sum(1 for d,pg in zip(dep_v,pg_v) if d < pg)
    draws   = n - wins_pg - wins_d

    print(f"\n  DEPSO:    {avg_d:.2f} LU  (vs SOP: {gap_d:.2f}%)")
    print(f"  PG-Final: {avg_pg:.2f} LU  (vs SOP: {gap_pg:.2f}%)")
    print(f"  PG vs DEPSO: {gap_pgd:+.2f}%")
    print(f"  PG wins: {wins_pg}/40  DEPSO wins: {wins_d}/40  Draws: {draws}/40")
    gc.collect()

    return {
        "Scenario":          scenario,
        "DEPSO_Avg":         round(avg_d, 2),
        "PG_Final_Avg":      round(avg_pg, 2),
        "SOP_Avg":           round(avg_sop, 2),
        "Gap_DEPSO_SOP_%":   round(gap_d, 2),
        "Gap_PG_SOP_%":      round(gap_pg, 2),
        "Gap_PG_vs_DEPSO_%": round(gap_pgd, 2),
        "PG_Wins":           wins_pg,
        "DEPSO_Wins":        wins_d,
        "Draws":             draws,
        "RT_DEPSO_Avg":      round(sum(rtd_v)/n, 2),
        "RT_PG_Avg":         round(sum(rtpg_v)/n, 2),
    }


if __name__ == "__main__":
    os.makedirs("../data", exist_ok=True)
    csv_path = "../data/DEPSO_vs_PG_Final.csv"

    scenarios = [
        (50,2,6),(50,2,10),(50,6,2),(50,6,6),(50,6,10),
        (50,10,2),(50,10,6),(50,10,10),
        (100,2,2),(100,2,6),(100,2,10),(100,6,2),(100,6,6),(100,6,10),
        (100,10,2),(100,10,6),(100,10,10),
        (150,2,2),(150,2,6),(150,2,10),(150,6,2),(150,6,6),(150,6,10),
        (150,10,2),(150,10,6),(150,10,10),
        (200,2,2),(200,2,6),(200,2,10),(200,6,2),(200,6,6),(200,6,10),
        (200,10,2),(200,10,6),(200,10,10),
    ]

    fieldnames = [
        "Scenario","DEPSO_Avg","PG_Final_Avg","SOP_Avg",
        "Gap_DEPSO_SOP_%","Gap_PG_SOP_%","Gap_PG_vs_DEPSO_%",
        "PG_Wins","DEPSO_Wins","Draws","RT_DEPSO_Avg","RT_PG_Avg"
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    total_start = time.time()

    for i, s in enumerate(scenarios):
        print(f"\n[{i+1}/{len(scenarios)}]")
        r = run_scenario(s[0], s[1], s[2], num_instances=40)
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=fieldnames).writerow(r)

    print(f"\n✅ DONE! Time: {(time.time()-total_start)/3600:.2f}h")
    print(f"📊 {csv_path}")