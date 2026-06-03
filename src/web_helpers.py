import math
import random
import numpy as np
import utils


class WebItem:
    def __init__(self, item_id, location_index):
        self.id = item_id
        self.location_index = location_index


warehouse_initialized = False


def initialize_warehouse():
    """
    Streamlit app için warehouse layout'u ve distance matrix'i hazırlar.
    Sadece bir kez çalıştırılması yeterlidir.
    """
    global warehouse_initialized

    if warehouse_initialized and utils.dist_matrix is not None:
        return

    locations = [
        utils.Location(
            index=0,
            aisle_id=0,
            rack_pos=0,
            side=1,
            slot=0
        )
    ]

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


def generate_demo_instance(num_orders, max_ol, max_parts_ol, seed=42):
    """
    Makaledeki Section 6.1 test verisi mantığına uygun tek demo instance üretir.
    Web app'te canlı demo için kullanılır.
    """
    initialize_warehouse()

    utils.set_seed(seed)
    utils.item_weights.clear()
    utils.route_cache.clear()

    items = []

    for i in range(1, 6001):
        item = WebItem(item_id=f"I_{i}", location_index=i)
        items.append(item)
        utils.item_weights[item.id] = random.uniform(0.1, 1.0)

    c = math.log10(0.6) / math.log10(0.2)

    cumulative_probs = []
    n_item = len(items)

    for y_idx in range(1, n_item + 1):
        y_norm = y_idx / n_item
        cumulative_probs.append(y_norm ** c)

    selection_weights = [cumulative_probs[0]]

    for i in range(1, len(cumulative_probs)):
        selection_weights.append(cumulative_probs[i] - cumulative_probs[i - 1])

    orders = []

    for k in range(num_orders):
        num_lines = random.randint(1, max_ol)

        unique_selected = set()

        while len(unique_selected) < num_lines:
            needed = num_lines - len(unique_selected)
            candidates = random.choices(
                items,
                weights=selection_weights,
                k=max(needed * 2, 1)
            )

            for item in candidates:
                unique_selected.add(item)

                if len(unique_selected) == num_lines:
                    break

        order_lines = []

        for item in list(unique_selected):
            quantity = random.randint(1, max_parts_ol)
            order_lines.append((item, quantity))

        orders.append(
            utils.Order(
                order_id=f"O_{k + 1}",
                lines=order_lines
            )
        )

    return orders


def parse_scenario_name(scenario_name):
    """
    '100_2_6' -> (100, 2, 6)
    """
    parts = scenario_name.split("_")
    return int(parts[0]), int(parts[1]), int(parts[2])


def get_all_scenarios():
    """
    Makaledeki 35 senaryo.
    50_2_2 hariç tutulur.
    """
    scenarios = []

    for num_orders in [50, 100, 150, 200]:
        for max_ol in [2, 6, 10]:
            for max_parts in [2, 6, 10]:
                if num_orders == 50 and max_ol == 2 and max_parts == 2:
                    continue

                scenarios.append(f"{num_orders}_{max_ol}_{max_parts}")

    return scenarios