import numpy as np
import random
import copy

# ==========================================
# 1. CONSTANTS & SYSTEM PARAMETERS
# ==========================================
CAPACITY = 100
DEPOT_INDEX = 0
CROSS_AISLES = [0, 30, 60, 90]
AISLE_SPACING = 2
CROSS_AISLE_PENALTY = 1

dist_matrix = None
item_weights = {}
route_cache = {}
locations_cache = [] # FIXED: Added for benchmark access

# ==========================================
# 2. DATA STRUCTURES (CLASSES)
# ==========================================
class Location:
    def __init__(self, index, aisle_id, rack_pos, side, slot):
        self.index = index
        self.aisle_id = aisle_id
        self.rack_pos = rack_pos
        self.side = side
        self.slot = slot

class Order:
    def __init__(self, order_id, lines):
        self.id = order_id
        self.lines = lines
        # Ağırlığı nesne yaratılırken bir kez hesapla
        self.weight = sum(item_weights[item.id] * quantity for (item, quantity) in lines)

def get_order_weight(order):
    return order.weight

class Particle:
    def __init__(self):
        self.pos = []
        self.vel = []
        self.fitness = float('inf')
        self.best_pos = []
        self.best_fitness = float('inf')

# ==========================================
# 3. REPRODUCIBILITY & DISTANCE MATRIX
# ==========================================

def clone_particle(p):
    new_p = Particle()
    new_p.pos = list(p.pos)
    new_p.vel = list(p.vel)
    new_p.fitness = p.fitness
    new_p.best_pos = list(p.best_pos)
    new_p.best_fitness = p.best_fitness
    return new_p


def set_seed(seed_value):
    random.seed(seed_value)
    np.random.seed(seed_value)

def calculate_distance(loc1, loc2):
    a1, rp1 = loc1.aisle_id, loc1.rack_pos
    a2, rp2 = loc2.aisle_id, loc2.rack_pos
    if a1 == a2:
        return abs(rp1 - rp2)
    min_dist = float('inf')
    for cp in CROSS_AISLES:
        dist = (abs(rp1 - cp) +
                abs(a1 - a2) * AISLE_SPACING +
                abs(rp2 - cp))
        if a1 != a2:
            dist += CROSS_AISLE_PENALTY
        if dist < min_dist:
            min_dist = dist
    return min_dist

def create_distance_matrix(location_list):
    """Builds the matrix and stores locations in cache for Section 7 benchmarks"""
    global dist_matrix, locations_cache
    locations_cache = location_list # FIXED: Populate the cache
    n_nodes = len(location_list)
    dist_matrix = np.zeros((n_nodes, n_nodes), dtype=np.int16)
    for i in range(n_nodes):
        for j in range(i, n_nodes):
            dist = calculate_distance(location_list[i], location_list[j])
            dist_matrix[i][j] = dist
            dist_matrix[j][i] = dist

# ==========================================
# 4. ROUTING, BATCHING & DISTANCE CALC
# ==========================================
def calculate_route_distance(tour):
    """CORE FUNCTION: Calculates total distance of a given tour list"""
    return sum(dist_matrix[tour[i]][tour[i + 1]] for i in range(len(tour) - 1))

def get_order_weight(order):
    return sum(item_weights[item.id] * quantity for (item, quantity) in order.lines)

def unique_locations(batch):
    seen = set()
    result = []
    for order in batch:
        for item, _ in order.lines:
            loc = item.location_index
            if loc not in seen:
                seen.add(loc)
                result.append(loc)
    return result

def nearest_neighbor(location_indices):
    if not location_indices:
        return [DEPOT_INDEX, DEPOT_INDEX]
    tour = [DEPOT_INDEX]
    unvisited = list(location_indices)
    current = DEPOT_INDEX
    while unvisited:
        nearest = min(unvisited, key=lambda t: dist_matrix[current][t])
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    tour.append(DEPOT_INDEX)
    return tour

def two_opt(tour, max_passes=3):
    n= len(tour)
    for _ in range(max_passes):
        improved = False

        for q in range(1, n - 2):
            for r in range(q + 1, n - 1):
                d_before = (
                    dist_matrix[tour[q - 1]][tour[q]] +
                    dist_matrix[tour[r]][tour[r + 1]]
                )

                d_after = (
                    dist_matrix[tour[q - 1]][tour[r]] +
                    dist_matrix[tour[q]][tour[r + 1]]
                )

                if d_after < d_before:
                    # Yerinde (in-place) ters çevirme, sıfır bellek yükü                   
                    tour[q:r + 1] = tour[q:r + 1][::-1]
                    improved = True

        if not improved:
            break

    return tour

def first_fit_batching(permutation):
    batches = []
    batch_weights = []
    for order in permutation:
        added = False
        for i in range(len(batches)):
            if batch_weights[i] + get_order_weight(order) <= CAPACITY:
                batches[i].append(order)
                batch_weights[i] += get_order_weight(order)
                added = True
                break
        if not added:
            batches.append([order])
            batch_weights.append(get_order_weight(order))
    return batches

def calculate_fitness(permutation):
    batches = first_fit_batching(permutation)
    total_distance = 0

    for batch in batches:
        locations = unique_locations(batch)
        total_distance += get_cached_route_dist(locations)

    return total_distance

def get_cached_route_dist(locs):
    """
    Returns cached route distance for a set of locations.
    Uses frozenset instead of sorted tuple to avoid repeated sorting cost.
    """
    if not locs:
        return 0

    key = frozenset(locs)

    if key in route_cache:
        return route_cache[key]

    route = nearest_neighbor(locs)
    route = two_opt(route)
    dist = calculate_route_distance(route)

    route_cache[key] = dist

    return dist

def savings_algorithm(orders):
    savings = []
    for i in range(len(orders)):
        for j in range(i + 1, len(orders)):
            o1, o2 = orders[i], orders[j]
            if get_order_weight(o1) + get_order_weight(o2) <= CAPACITY:
                locs1 = unique_locations([o1])
                locs2 = unique_locations([o2])
                locs12 = unique_locations([o1, o2])
                d1 = get_cached_route_dist(locs1)
                d2 = get_cached_route_dist(locs2)
                d12 = get_cached_route_dist(locs12)
                sav = d1 + d2 - d12
                savings.append((sav, o1, o2))
    savings.sort(key=lambda x: x[0], reverse=True)
    batch_dict = {}
    batches = []
    for sav, o1, o2 in savings:
        idx1 = batch_dict.get(o1.id)
        idx2 = batch_dict.get(o2.id)
        if idx1 is None and idx2 is None:
            idx = len(batches)
            batches.append([o1, o2])
            batch_dict[o1.id] = idx
            batch_dict[o2.id] = idx
        elif idx1 is not None and idx2 is None:
            if sum(get_order_weight(o) for o in batches[idx1]) + get_order_weight(o2) <= CAPACITY:
                if o2 not in batches[idx1]:
                    batches[idx1].append(o2)
                    batch_dict[o2.id] = idx1
        elif idx2 is not None and idx1 is None:
            if sum(get_order_weight(o) for o in batches[idx2]) + get_order_weight(o1) <= CAPACITY:
                if o1 not in batches[idx2]:
                    batches[idx2].append(o1)
                    batch_dict[o1.id] = idx2
    for o in orders:
        if o.id not in batch_dict:
            batches.append([o])
    permutation = []
    for b in batches:
        permutation.extend(b)
    
    return permutation

# ==========================================
# 5. DEPSO CORE OPERATORS
# ==========================================
def calculate_difference(perm1, perm2):
    k_len = len(perm1)
    return sum(1 for j in range(k_len) if perm1[j].id != perm2[j].id) / k_len

def particle_movement(p_pos, p_vel, p_best_pos, g_best_pos, threshold_gbest, v_p=0.5):
    k_len = len(p_pos)
    new_pos = list(p_pos)
    prob_pbest = calculate_difference(new_pos, p_best_pos)
    prob_gbest = calculate_difference(new_pos, g_best_pos)
    pos_map = {order.id: idx for idx, order in enumerate(new_pos)}
    for h in range(k_len):
        if p_vel[h] == 1 and prob_gbest > (threshold_gbest * random.random()):
            g_item = g_best_pos[h]
            r_idx = pos_map[g_item.id]
            id_h = new_pos[h].id
            id_r = new_pos[r_idx].id
            new_pos[h], new_pos[r_idx] = new_pos[r_idx], new_pos[h]
            pos_map[id_h] = r_idx
            pos_map[id_r] = h
        elif p_vel[h] == -1 and prob_pbest > (v_p * random.random()):
            p_item = p_best_pos[h]
            r_idx = pos_map[p_item.id]
            id_h = new_pos[h].id
            id_r = new_pos[r_idx].id
            new_pos[h], new_pos[r_idx] = new_pos[r_idx], new_pos[h]
            pos_map[id_h] = r_idx
            pos_map[id_r] = h
        p_vel[h] = random.choice([-1, 0, 1])
    return new_pos, p_vel

def random_two_indices(k_len):
    if k_len < 2: return 0, 0
    i = random.randint(0, k_len - 1)
    j = random.randint(0, k_len - 1)
    while i == j: j = random.randint(0, k_len - 1)
    return i, j


def apply_mutation(particles, g_best):
    intensities = []
    for p in particles:
        d1 = calculate_difference(p.pos, p.best_pos)
        d2 = calculate_difference(p.pos, g_best.pos)
        d3 = calculate_difference(p.best_pos, g_best.pos)
        intensities.append((d1 + d2 + d3) / 3.0)
    int_max = max(intensities)
    int_min = min(intensities)
    for idx, p in enumerate(particles):
        m_prob = (int_max - intensities[idx]) / (int_max - int_min) if int_max != int_min else 1.0
        if random.random() < m_prob:
            td_max = max(p2.fitness for p2 in particles)
            cl_p = (p.fitness - g_best.fitness) / (td_max - g_best.fitness) if td_max != g_best.fitness else 0.0
            if cl_p < 0.5:
                i, j = random_two_indices(len(p.pos))
                p.pos[i], p.pos[j] = p.pos[j], p.pos[i]
            elif cl_p < 0.8:
                i, j = random_two_indices(len(p.pos))
                p.pos.insert(j, p.pos.pop(i))
            else:
                i, j = sorted(random_two_indices(len(p.pos)))
                p.pos[i:j + 1] = p.pos[i:j + 1][::-1]
            k_len = len(p.pos)
            i, j = random_two_indices(k_len)
            p.vel[i] = random.choice([-1, 0, 1])
            p.vel[j] = random.choice([-1, 0, 1])
            p.fitness = calculate_fitness(p.pos)
            if p.fitness < p.best_fitness:
                p.best_pos = list(p.pos)
                p.best_fitness = p.fitness


def local_search(g_best, max_ls_iter, particles):
    current_ls_iter = 0
    k_len = len(g_best.pos)

    while current_ls_iter < max_ls_iter:
        candidate_pos = list(g_best.pos)

        i, j = random_two_indices(k_len)
        candidate_pos[i], candidate_pos[j] = candidate_pos[j], candidate_pos[i]

        candidate_fitness = calculate_fitness(candidate_pos)

        if candidate_fitness < g_best.fitness:
            g_best.pos = candidate_pos
            g_best.fitness = candidate_fitness
            g_best.best_pos = list(candidate_pos)
            g_best.best_fitness = candidate_fitness

            rand_particle = random.choice(particles)
            rand_particle.pos = list(g_best.pos)
            rand_particle.fitness = g_best.fitness

            if g_best.fitness < rand_particle.best_fitness:
                rand_particle.best_pos = list(g_best.pos)
                rand_particle.best_fitness = g_best.fitness

            return g_best, 0

        current_ls_iter += 1

    return g_best, 1
# ==========================================
# 6. MAIN DEPSO ALGORITHM
# ==========================================
def run_depso(orders, num_particles, max_iterations, threshold_gbest, max_ls_iter, max_stagnation, v_p=0.5):
    global route_cache
    route_cache.clear()
    k_len = len(orders)
    particles = []
    convergence_curve = []
    for _ in range(num_particles - 1):
        p = Particle()
        p.pos = list(orders)
        random.shuffle(p.pos)
        p.vel = [random.choice([-1, 0, 1]) for _ in range(k_len)]
        p.fitness = calculate_fitness(p.pos)
        p.best_pos = list(p.pos)
        p.best_fitness = p.fitness
        particles.append(p)
    sav_p = Particle()
    sav_p.pos = savings_algorithm(orders)
    sav_p.vel = [random.choice([-1, 0, 1]) for _ in range(k_len)]
    sav_p.fitness = calculate_fitness(sav_p.pos)
    sav_p.best_pos = list(sav_p.pos)
    sav_p.best_fitness = sav_p.fitness
    particles.append(sav_p)
    g_best = clone_particle(min(particles, key=lambda p: p.fitness))  
    stagnation_counter = 0
    for current_iter in range(1, max_iterations + 1):
        gbest_updated = False
        for p in particles:
            p.pos, p.vel = particle_movement(p.pos, p.vel, p.best_pos, g_best.pos, threshold_gbest, v_p)
            p.fitness = calculate_fitness(p.pos)
            if p.fitness < p.best_fitness:
                p.best_pos = list(p.pos)
                p.best_fitness = p.fitness
            if p.fitness < g_best.fitness:
                g_best = clone_particle(p)
                stagnation_counter = 0
                gbest_updated = True
        if not gbest_updated:
            stagnation_counter += 1
        apply_mutation(particles, g_best)
        for p in particles:
            if p.fitness < g_best.fitness:
                g_best = clone_particle(p)
                stagnation_counter = 0
        adaptive_stag_threshold = round(1 + max_stagnation * (max_iterations - current_iter) / max_iterations)
        if stagnation_counter > adaptive_stag_threshold * random.random():
            g_best, _ = local_search(g_best, max_ls_iter, particles)
            stagnation_counter = 0


        convergence_curve.append(g_best.fitness)
        
        # Early stopping condition
        patience = 100
        min_improvement = 0.001

        if len(convergence_curve) > patience:
            previous_best = convergence_curve[-patience]
            current_best = convergence_curve[-1]

            improvement = (previous_best - current_best) / previous_best

            if improvement < min_improvement:
                print(f"Early stopping at iteration {current_iter}")
                break
    final_batches = first_fit_batching(g_best.pos)
    final_routes = []
    for batch in final_batches:
        locations = unique_locations(batch)
        route = two_opt(nearest_neighbor(locations))
        final_routes.append(route)
    return final_batches, final_routes, g_best.fitness, convergence_curve

## =========================================================================
# 7. BENCHMARK ALGORITHMS (S-Shape, SOP, FCFS) - OVERFLOW ENGELLEMELİ TAM KOD 🚀
# =========================================================================
def s_shape_route(location_indices, locations_objects):
    """Zigzag pattern: Standard S-Shape heuristic [Section 7.1]"""
    if not location_indices:
        return [0, 0]
    aisles_with_items = sorted(list(set(locations_objects[idx].aisle_id for idx in location_indices)))
    route = [0]
    direction = 1
    for aisle_id in aisles_with_items:
        aisle_items = [locations_objects[idx] for idx in location_indices if locations_objects[idx].aisle_id == aisle_id]
        sorted_aisle = sorted(aisle_items, key=lambda x: x.rack_pos, reverse=(direction == -1))
        for loc in sorted_aisle:
            route.append(loc.index)
        direction *= -1
    route.append(0)
    return route

def calculate_sop_distance(orders, locations_objects):
    """Section 7.2: Single Order Picking (No batching)"""
    # Standart Python int yapısı kullanılarak taşma engellendi
    total_dist = 0
    for order in orders:
        loc_indices = list(set(line[0].location_index for line in order.lines))
        route = s_shape_route(loc_indices, locations_objects)
        # int() cast işlemi ile numpy.int16 sınırları standart int'e taşındı 🚀
        total_dist += int(calculate_route_distance(route))
    return total_dist

def calculate_fcfs_distance(orders, locations_objects):
    """Section 7.3: First-Come-First-Served Batching"""
    batches = first_fit_batching(orders)
    # Standart Python int yapısı kullanılarak taşma engellendi
    total_dist = 0
    for batch in batches:
        loc_indices = unique_locations(batch)
        route = s_shape_route(loc_indices, locations_objects)
        # int() cast işlemi ile numpy.int16 sınırları standart int'e taşındı 🚀
        total_dist += int(calculate_route_distance(route))
    return total_dist

def calculate_savings_distance(orders, locations_objects):
    """Section 7.4: Clarke & Wright Savings + S-Shape Routing"""
    # Savings-based permutation
    savings_perm = savings_algorithm(orders)

    # Convert permutation into batches
    batches = first_fit_batching(savings_perm)

    # Standart Python int yapısı kullanılarak taşma engellendi
    total_dist = 0

    for batch in batches:
        # Unique pick locations
        loc_indices = unique_locations(batch)

        # S-Shape route
        route = s_shape_route(loc_indices, locations_objects)

        # Route distance - int() cast işlemi ile numpy.int16 sınırları standart int'e taşındı 🚀
        total_dist += int(calculate_route_distance(route))
    return total_dist