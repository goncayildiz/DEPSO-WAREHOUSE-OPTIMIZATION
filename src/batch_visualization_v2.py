"""
batch_visualization_v2.py
==========================
Kullanim: En üstteki 3 satiri degistirerek istediginiz senaryoyu test edin.

    NUM_ORDERS  = 50    # Siparis sayisi: 50, 100, 150, 200
    MAX_OL      = 6     # Maks. orderline/siparis: 2, 6, 10
    MAX_PARTS   = 6     # Maks. parca/orderline: 2, 6, 10

Ciktilar:
  batch_olusumu_<senaryo>.png   — Kapasite bar chart + akis tablosu
  depo_rota_<senaryo>.png       — Depo uzerinde S-Shape rotalar
  batch_ozet_<senaryo>.txt      — Metin ozeti
"""

import sys, os
sys.path.insert(0, os.path.expanduser('~/src'))   # main.py'nin bulundugu klasor

# ══════════════════════════════════════════════════════════════════════
#  BURAYA ISTEDIGINIZ SENARYOYU YAZIN — sadece bu 3 satir degisecek
# ══════════════════════════════════════════════════════════════════════
NUM_ORDERS = 50   # 50 | 100 | 150 | 200
MAX_OL     = 10   # 2  | 6   | 10
MAX_PARTS  = 10    # 2  | 6   | 10
SEED       = 42    # herhangi bir sayi — tekrarlanabilirlik icin
# ══════════════════════════════════════════════════════════════════════

import random, math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.spines.top']   = False
plt.rcParams['axes.spines.right'] = False

SCENARIO  = f"{NUM_ORDERS}_{MAX_OL}_{MAX_PARTS}"
CAPACITY  = 100.0
AISLE_SPACING = 2
CROSS_AISLES  = [0, 30, 60, 90]
COLORS = ['#185FA5','#E24B4A','#3B6D11','#BA7517','#534AB7',
          '#993556','#1D9E75','#D85A30','#7F77DD','#4A4A4A']

print(f"Senaryo: {SCENARIO} | Seed: {SEED}")

# ══════════════════════════════════════════════════════════════════════
# 1. SENARYO VERİSİNİ ÜRET — main.py mantığının kopyası
#    (main.py'yi import etmek yerine burada kendi kendine üretiyor,
#     böylece src klasöründe olmak zorunda değilsiniz)
# ══════════════════════════════════════════════════════════════════════
random.seed(SEED)
np.random.seed(SEED)

# Depo: 10 koridor × 2 yön × 90 raf × 4 slot = 7200 lokasyon
item_weights_map = {}
locations_list   = []   # (index, aisle, rack, side, slot)

# Depot lokasyonu (index=0)
locations_list.append({'index': 0, 'aisle': 0, 'rack': 0, 'side': 0, 'slot': 0})

idx = 1
for aisle in range(1, 11):
    for side in range(1, 3):
        for rack in range(1, 91):
            for slot in range(1, 5):
                locations_list.append({
                    'index': idx, 'aisle': aisle,
                    'rack': rack, 'side': side, 'slot': slot
                })
                idx += 1

# 6000 ürün — AF=0.6 Pareto dağılımı
n_items = 6000
c = math.log10(0.6) / math.log10(0.2)
cum_probs = [(y / n_items) ** c for y in range(1, n_items + 1)]
sel_weights = [cum_probs[0]] + [cum_probs[i] - cum_probs[i-1]
                                  for i in range(1, n_items)]

class FakeItem:
    def __init__(self, item_id, loc_index):
        self.id = item_id
        self.location_index = loc_index

items_pool = [FakeItem(f"I_{i}", i) for i in range(1, n_items + 1)]
for item in items_pool:
    item_weights_map[item.id] = random.uniform(0.1, 1.0)

class Order:
    def __init__(self, order_id, lines):
        self.id = order_id
        self.lines = lines
        self.weight = sum(item_weights_map[it.id] * qty for it, qty in lines)

orders = []
for k in range(NUM_ORDERS):
    num_lines  = random.randint(1, MAX_OL)
    unique_sel = set()
    while len(unique_sel) < num_lines:
        needed     = num_lines - len(unique_sel)
        candidates = random.choices(items_pool, weights=sel_weights, k=needed * 2)
        for itm in candidates:
            unique_sel.add(itm)
            if len(unique_sel) == num_lines:
                break
    order_lines = []
    for itm in list(unique_sel):
        parts = random.randint(1, MAX_PARTS)
        order_lines.append((itm, parts))
    orders.append(Order(order_id=f"O_{k+1}", lines=order_lines))

print(f"Uretilen siparis sayisi: {len(orders)}")
print(f"Ortalama siparis agirligi: "
      f"{sum(o.weight for o in orders)/len(orders):.2f} WU")

# ══════════════════════════════════════════════════════════════════════
# 2. FIRST-FIT BATCHING
# ══════════════════════════════════════════════════════════════════════
batches    = []
batch_wts  = []
batch_log  = []

for order in orders:
    w = order.weight
    placed = False
    for i, (batch, bw) in enumerate(zip(batches, batch_wts)):
        if bw + w <= CAPACITY:
            batch.append(order)
            batch_wts[i] += w
            batch_log.append({
                'Siparis':             order.id,
                'Agirlik (WU)':        round(w, 2),
                'Atandigi Batch':      f'Batch {i+1}',
                'Batch Toplam Sonra':  round(batch_wts[i], 2),
                'Durum':               'Eklendi'
            })
            placed = True
            break
    if not placed:
        batches.append([order])
        batch_wts.append(w)
        batch_log.append({
            'Siparis':             order.id,
            'Agirlik (WU)':        round(w, 2),
            'Atandigi Batch':      f'Batch {len(batches)}',
            'Batch Toplam Sonra':  round(w, 2),
            'Durum':               'Yeni Batch'
        })

print(f"Olusturulan batch sayisi: {len(batches)}")
for i, (b, w) in enumerate(zip(batches, batch_wts)):
    print(f"  Batch {i+1:2d}: {len(b):3d} siparis | "
          f"{w:.2f} WU | doluluk %{w/CAPACITY*100:.0f}")

# ══════════════════════════════════════════════════════════════════════
# 3. S-SHAPE ROUTING
# ══════════════════════════════════════════════════════════════════════
def depot_xy():
    return (91, 0)

def s_shape_route(batch_orders):
    # Tüm benzersiz (aisle, rack) konumlarını topla
    loc_by_aisle = {}
    for order in batch_orders:
        for item, qty in order.lines:
            loc_idx = item.location_index
            if 1 <= loc_idx <= len(locations_list) - 1:
                loc = locations_list[loc_idx]
                a, r = loc['aisle'], loc['rack']
                if a not in loc_by_aisle:
                    loc_by_aisle[a] = []
                loc_by_aisle[a].append({'rack': r, 'item_id': item.id,
                                         'loc_idx': loc_idx})

    if not loc_by_aisle:
        return [depot_xy(), depot_xy()], 0.0

    aisles_used = sorted(loc_by_aisle.keys())
    route_xy    = [depot_xy()]
    dist_total  = 0.0
    cur_x, cur_y = depot_xy()

    for idx, aisle in enumerate(aisles_used):
        is_last = (idx == len(aisles_used) - 1)
        aisle_y = (aisle - 1) * AISLE_SPACING
        items_here = sorted(loc_by_aisle[aisle], key=lambda l: l['rack'])

        # Koridora git (yatay + dikey hareket)
        dist_total += abs(cur_y - aisle_y)
        cur_y = aisle_y
        route_xy.append((cur_x, cur_y))

        if not is_last:
            # S-Shape: koridoru tamamen kat et
            if idx % 2 == 0:
                end_x = 90
            else:
                end_x = 1
            dist_total += abs(end_x - cur_x)
            cur_x = end_x
            route_xy.extend([(item['rack'], aisle_y)
                              for item in items_here])
            route_xy.append((cur_x, cur_y))
        else:
            # Son koridor: sadece en uzak ürüne git
            if idx % 2 == 0:
                end_x = max(i['rack'] for i in items_here)
            else:
                end_x = min(i['rack'] for i in items_here)
            dist_total += abs(end_x - cur_x)
            cur_x = end_x
            route_xy.extend([(item['rack'], aisle_y)
                              for item in items_here])

        # Çapraz yola geç
        if not is_last:
            cp = 90 if cur_x > 45 else 0
            dist_total += abs(cur_x - cp)
            cur_x = cp

    # Depot'a dön
    dx, dy = depot_xy()
    dist_total += abs(cur_x - dx) + abs(cur_y - dy)
    cur_x, cur_y = dx, dy
    route_xy.append((cur_x, cur_y))

    return route_xy, dist_total

batch_routes = []
for i, (batch, bw) in enumerate(zip(batches, batch_wts)):
    route_xy, dist = s_shape_route(batch)
    # Batch'teki tüm lokasyonları topla (görseller için)
    locs_info = []
    for order in batch:
        for item, qty in order.lines:
            li = item.location_index
            if 1 <= li <= len(locations_list) - 1:
                loc = locations_list[li]
                locs_info.append({'item_id': item.id,
                                   'aisle': loc['aisle'],
                                   'rack':  loc['rack']})
    batch_routes.append({
        'batch_id':  i + 1,
        'orders':    [o.id for o in batch],
        'locations': locs_info,
        'route':     route_xy,
        'distance':  dist,
        'weight':    bw
    })

# ══════════════════════════════════════════════════════════════════════
# 4. GRAFİK A — BATCH KAPASİTE ANALİZİ
# ══════════════════════════════════════════════════════════════════════
fig1 = plt.figure(figsize=(max(14, len(batches) * 1.4), 7))
gs   = gridspec.GridSpec(1, 2, width_ratios=[1.6, 1], figure=fig1)
ax_bar  = fig1.add_subplot(gs[0])
ax_info = fig1.add_subplot(gs[1])

bar_colors = [COLORS[i % len(COLORS)] for i in range(len(batches))]
bars = ax_bar.bar([f'B{i+1}' for i in range(len(batches))],
                  batch_wts, color=bar_colors, alpha=0.85,
                  edgecolor='white', linewidth=0.5, zorder=3)

ax_bar.axhline(CAPACITY, color='#E24B4A', linewidth=2.2,
               linestyle='--', zorder=5, label='100 WU Kapasite Siniri')
ax_bar.text(len(batches) - 0.4, 102,
            '100 WU SINIR', color='#E24B4A',
            fontsize=8, fontweight='bold', ha='right')

for bar, wt in zip(bars, batch_wts):
    ax_bar.text(bar.get_x() + bar.get_width()/2, wt + 0.5,
                f'{wt:.1f}\n%{wt/CAPACITY*100:.0f}',
                ha='center', va='bottom', fontsize=7.5,
                fontweight='bold', color='#333333')

ax_bar.set_xlabel('Batch', fontsize=11, fontweight='bold')
ax_bar.set_ylabel('Toplam Agirlik (WU)', fontsize=11, fontweight='bold')
ax_bar.set_title(
    f'Batch Kapasite Analizi — Senaryo: {SCENARIO}\n'
    f'{len(batches)} batch | {len(orders)} siparis | First-Fit Batching',
    fontsize=11, fontweight='bold', pad=10)
ax_bar.set_ylim(0, 115)
ax_bar.legend(fontsize=9)
ax_bar.grid(axis='y', alpha=0.3, linewidth=0.5, zorder=0)

# Sağ panel: akış tablosu
ax_info.axis('off')
ax_info.set_title('Batch Atama Akisi (Ilk 15)', fontsize=10,
                  fontweight='bold', pad=8)
show_n = min(15, len(batch_log))
tbl_data = [[r['Siparis'], f"{r['Agirlik (WU)']} WU",
             r['Atandigi Batch'],
             f"{r['Batch Toplam Sonra']} WU",
             r['Durum']] for r in batch_log[:show_n]]
row_colors = [['#FFF3CD'] * 5 if 'Yeni' in r['Durum']
              else ['#F0F7FF'] * 5
              for r in batch_log[:show_n]]
tbl = ax_info.table(
    cellText=tbl_data,
    colLabels=['Siparis', 'Agirlik', 'Batch', 'Toplam', 'Durum'],
    cellLoc='center', loc='upper center',
    bbox=[0, 0.02, 1.0, 0.95])
tbl.auto_set_font_size(False)
tbl.set_fontsize(8)
for (r, c), cell in tbl.get_celld().items():
    if r == 0:
        cell.set_facecolor('#1F4E79')
        cell.set_text_props(color='white', fontweight='bold')
    elif r <= show_n:
        cell.set_facecolor(row_colors[r-1][c])
    cell.set_edgecolor('#DDDDDD')

fig1.suptitle(
    f'DEPSO — Batch Olusumu | Senaryo {SCENARIO} | Seed {SEED}',
    fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
out1 = f'batch_olusumu_{SCENARIO}.png'
plt.savefig(out1, dpi=160, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Kaydedildi: {out1}')

# ══════════════════════════════════════════════════════════════════════
# 5. GRAFİK B — DEPO ROTA (ilk 4 veya tüm batch'ler ≤4)
# ══════════════════════════════════════════════════════════════════════
n_show  = min(4, len(batch_routes))
ncols   = min(2, n_show)
nrows   = math.ceil(n_show / ncols)

fig2, axes = plt.subplots(nrows, ncols, figsize=(11 * ncols, 8 * nrows))
if n_show == 1:
    axes = np.array([[axes]])
elif nrows == 1:
    axes = axes.reshape(1, -1)

fig2.suptitle(
    f'Depo Rota Gorunumu — S-Shape Routing | Senaryo {SCENARIO} | Seed {SEED}\n'
    '10 Koridor × 90 Raf × 3 Blok | Manhattan Metrik | Depot: Sag Alt',
    fontsize=12, fontweight='bold', y=1.01)

for plot_i in range(nrows * ncols):
    row_i, col_i = divmod(plot_i, ncols)
    ax = axes[row_i][col_i]

    if plot_i >= n_show:
        ax.axis('off')
        continue

    br    = batch_routes[plot_i]
    color = COLORS[plot_i % len(COLORS)]

    # Depo arka plan
    for a in range(1, 11):
        y = (a - 1) * AISLE_SPACING
        ax.fill_between([0, 92], [y-0.25, y-0.25], [y+0.25, y+0.25],
                        color='#F4F4F2', alpha=0.9, zorder=1)
        ax.text(-1, y, f'K{a}', fontsize=7, ha='right',
                va='center', color='#555555', fontweight='bold')

    for cp in CROSS_AISLES:
        ax.axvline(cp, color='#CCCCCC', linewidth=1.0,
                   linestyle='-', alpha=0.8, zorder=2)

    # Blok etiketleri
    for blk, xp in [('Blok 1', 15), ('Blok 2', 45), ('Blok 3', 75)]:
        ax.text(xp, 19.2, blk, fontsize=7, ha='center',
                color='#777777',
                bbox=dict(boxstyle='round,pad=0.2',
                          facecolor='#EEEEEE',
                          edgecolor='#CCCCCC', alpha=0.7))

    # Bu batch'teki ürün noktaları
    seen_locs = set()
    for loc in br['locations']:
        key = (loc['aisle'], loc['rack'])
        if key not in seen_locs:
            x = loc['rack']
            y = (loc['aisle'] - 1) * AISLE_SPACING
            ax.plot(x, y, 'o', color=color, markersize=7,
                    zorder=6, markeredgecolor='white',
                    markeredgewidth=0.8)
            seen_locs.add(key)

    # Rota çizgisi
    route = br['route']
    if len(route) > 1:
        rx = [p[0] for p in route]
        ry = [p[1] for p in route]
        ax.plot(rx, ry, '-', color=color, linewidth=1.8,
                alpha=0.65, zorder=4)
        # Ok uçları
        step = max(1, len(route) // 8)
        for k in range(0, len(route)-1, step):
            dx = route[k+1][0] - route[k][0]
            dy = route[k+1][1] - route[k][1]
            if abs(dx) + abs(dy) > 2:
                ax.annotate('', xy=route[k+1], xytext=route[k],
                            arrowprops=dict(arrowstyle='->',
                                           color=color, lw=1.4),
                            zorder=5)

    # Depot
    dep = depot_xy()
    ax.plot(dep[0], dep[1], 'D', color='#FFD700', markersize=13,
            zorder=9, markeredgecolor='#333333', markeredgewidth=1.5)
    ax.text(dep[0]-1, dep[1]+0.8, 'DEPOT', fontsize=8,
            color='#333333', fontweight='bold', ha='right', zorder=10)

    # Başlangıç noktası
    if route:
        ax.plot(route[0][0], route[0][1], 's', color='#FFD700',
                markersize=10, zorder=8,
                markeredgecolor='#333333', markeredgewidth=1)

    # Başlık
    aisles_used = sorted(set(l['aisle'] for l in br['locations']))
    ax.set_title(
        f"Batch {br['batch_id']} — {', '.join(br['orders'])}\n"
        f"Agirlik: {br['weight']:.1f}/{CAPACITY:.0f} WU "
        f"(%{br['weight']/CAPACITY*100:.0f})  |  "
        f"Mesafe: {br['distance']:.0f} LU  |  "
        f"Koridorlar: K{', K'.join(map(str, aisles_used))}",
        fontsize=8.5, fontweight='bold', color=color, pad=5)

    # Bilgi kutusu
    info = (f"Siparis: {len(br['orders'])}\n"
            f"Durak  : {len(seen_locs)}\n"
            f"Doluluk: %{br['weight']/CAPACITY*100:.0f}")
    ax.text(0.99, 0.99, info, transform=ax.transAxes,
            fontsize=8, va='top', ha='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor=color, alpha=0.9))

    ax.set_xlim(-3, 96)
    ax.set_ylim(-1.5, 20.5)
    ax.set_xlabel('Raf Pozisyonu', fontsize=8)
    ax.set_ylabel('Koridor', fontsize=8)
    ax.set_yticks([(a-1)*AISLE_SPACING for a in range(1, 11)])
    ax.set_yticklabels([f'K{a}' for a in range(1, 11)], fontsize=7)
    ax.grid(alpha=0.12, linewidth=0.4)

plt.tight_layout()
out2 = f'depo_rota_{SCENARIO}.png'
plt.savefig(out2, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Kaydedildi: {out2}')

# ══════════════════════════════════════════════════════════════════════
# 6. ÖZET TXT
# ══════════════════════════════════════════════════════════════════════
out3 = f'batch_ozet_{SCENARIO}.txt'
with open(out3, 'w') as f:
    f.write(f"BATCH & ROTA OZETI — Senaryo {SCENARIO} | Seed {SEED}\n")
    f.write("=" * 60 + "\n")
    f.write(f"Siparis: {len(orders)} | Batch: {len(batches)} | "
            f"Kapasite: {CAPACITY} WU\n")
    f.write(f"Batching: First-Fit | Routing: S-Shape + Manhattan\n\n")
    total_d = sum(br['distance'] for br in batch_routes)
    f.write(f"Toplam rota mesafesi: {total_d:.1f} LU\n\n")
    for br in batch_routes:
        aisles = sorted(set(l['aisle'] for l in br['locations']))
        f.write(f"Batch {br['batch_id']:2d}: {', '.join(br['orders'])}\n")
        f.write(f"  Agirlik : {br['weight']:.2f} WU | "
                f"Doluluk: %{br['weight']/CAPACITY*100:.0f} | "
                f"Mesafe: {br['distance']:.0f} LU\n")
        f.write(f"  Koridor : K{', K'.join(map(str, aisles))}\n\n")
print(f'Kaydedildi: {out3}')
print("\nTamamlandi!")
