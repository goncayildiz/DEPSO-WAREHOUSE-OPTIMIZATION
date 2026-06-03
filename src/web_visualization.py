import plotly.graph_objects as go
import utils


def loc_to_xy(loc):
    """
    Warehouse koordinat dönüşümü.
    x: aisle fiziksel pozisyonu
    y: rack pozisyonu
    """
    x = loc.aisle_id * utils.AISLE_SPACING
    y = loc.rack_pos
    return x, y


def get_best_cross_aisle(loc1, loc2):
    """
    İki lokasyon arasındaki en kısa corridor-safe geçiş için cross aisle seçer.
    """
    best_cp = None
    best_dist = float("inf")

    for cp in utils.CROSS_AISLES:
        dist = (
            abs(loc1.rack_pos - cp)
            + abs(loc1.aisle_id - loc2.aisle_id) * utils.AISLE_SPACING
            + abs(loc2.rack_pos - cp)
        )

        if dist < best_dist:
            best_dist = dist
            best_cp = cp

    return best_cp


def corridor_safe_segment(loc1, loc2):
    """
    İki lokasyon arasında rafların üzerinden geçmeyen çizgi segmenti üretir.

    Aynı aisle:
        dikey hareket

    Farklı aisle:
        lokasyon 1 -> en uygun cross aisle
        cross aisle üzerinde yatay hareket
        hedef aisle -> lokasyon 2
    """
    x1, y1 = loc_to_xy(loc1)
    x2, y2 = loc_to_xy(loc2)

    if loc1.aisle_id == loc2.aisle_id:
        return [(x1, y1), (x2, y2)]

    cp = get_best_cross_aisle(loc1, loc2)

    return [
        (x1, y1),
        (x1, cp),
        (x2, cp),
        (x2, y2),
    ]


def expand_route_to_corridor_path(route, locations):
    """
    DEPSO route node sequence'i corridor-safe polyline'a dönüştürür.
    """
    xs = []
    ys = []

    for i in range(len(route) - 1):
        loc1 = locations[route[i]]
        loc2 = locations[route[i + 1]]

        segment = corridor_safe_segment(loc1, loc2)

        for x, y in segment:
            xs.append(x)
            ys.append(y)

        xs.append(None)
        ys.append(None)

    return xs, ys


def get_batch_pick_points(batch):
    """
    Batch içindeki ürün lokasyonlarını marker olarak döndürür.
    """
    seen = set()
    xs = []
    ys = []
    texts = []

    for order in batch:
        for item, quantity in order.lines:
            loc_idx = item.location_index

            if loc_idx in seen:
                continue

            seen.add(loc_idx)

            loc = utils.locations_cache[loc_idx]
            x, y = loc_to_xy(loc)

            xs.append(x)
            ys.append(y)
            texts.append(
                f"Item: {item.id}<br>"
                f"Location: {loc_idx}<br>"
                f"Aisle: {loc.aisle_id}<br>"
                f"Rack: {loc.rack_pos}<br>"
                f"Qty: {quantity}"
            )

    return xs, ys, texts


def create_warehouse_figure(route, batch, title="Corridor-Safe Picker Route"):
    """
    Depo layout'unu, ürün noktalarını ve corridor-safe picker route'u çizer.
    """
    locations = utils.locations_cache

    fig = go.Figure()

    aisle_xs = [a * utils.AISLE_SPACING for a in range(10)]

    # Picking aisles
    for aisle_id, x in enumerate(aisle_xs):
        fig.add_trace(
            go.Scatter(
                x=[x, x],
                y=[0, 90],
                mode="lines",
                line=dict(width=2, color="#D0D0D0"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        fig.add_annotation(
            x=x,
            y=-4,
            text=f"Aisle {aisle_id}",
            showarrow=False,
            font=dict(size=10),
        )

    # Cross aisles
    for cp in utils.CROSS_AISLES:
        fig.add_trace(
            go.Scatter(
                x=[min(aisle_xs), max(aisle_xs)],
                y=[cp, cp],
                mode="lines",
                line=dict(width=3, color="#9A9A9A"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Pick points
    px, py, ptext = get_batch_pick_points(batch)

    fig.add_trace(
        go.Scatter(
            x=px,
            y=py,
            mode="markers",
            marker=dict(size=8, symbol="circle"),
            text=ptext,
            hoverinfo="text",
            name="Pick Locations",
        )
    )

    # Corridor-safe route
    route_x, route_y = expand_route_to_corridor_path(route, locations)

    fig.add_trace(
        go.Scatter(
            x=route_x,
            y=route_y,
            mode="lines",
            line=dict(width=4),
            name="Corridor-Safe Route",
        )
    )

    # Route order markers
    # Aynı fiziksel koordinata düşen step'şleri tek marker'da grupluyoruz.
    # Bunun sebebi: side ve slot farkları mesafe/görselleştirme hesabında ihmal ediliyor
    grouped_steps = {}

    for step, loc_idx in enumerate(route):
        loc = locations[loc_idx]
        x, y = loc_to_xy(loc)
        key = (x,y)

        if key not in grouped_steps:
            grouped_steps[key] = {
                "x": x,
                "y": y,
                "steps": [],
                "location_ids": [],
            }

            grouped_steps[key]["steps"].append(step)
            grouped_steps[key]["location_ids"].append(loc_idx)

    route_marker_x = []
    route_marker_y = []
    route_marker_text = []
    route_marker_labels = []

    for data in grouped_steps.values():
        route_marker_x.append(data["x"])
        route_marker_y.append(data["y"])

        steps_text =", ".join(str(s) for s in data["steps"])
        locs_text = ", ".join(str(1) for l in data["location_ids"])

        if len(data["steps"]) == 1:
            label = str(data["steps"][0])
        else:
            label = f"{data['steps'][0]}-{data['steps'][-1]}"

        route_marker_labels.append(label)

        route_marker_text.append(
            f"Steps: {steps_text}<br>"
            f"Location Ids: {locs_text}<br>"
            f"Same plotted point because side/slot are ignored"
        )
    
    fig.add_trace(
        go.Scatter(
            x=route_marker_x,
            y=route_marker_y,
            mode="markers+text",
            marker=dict(size=7),
            text=route_marker_labels,
            textposition="top center",
            hovertext=route_marker_text,
            hoverinfo="text",
            name="Route Sequence",
        )
    )

    # Depot
    depot = locations[utils.DEPOT_INDEX]
    depot_x, depot_y = loc_to_xy(depot)

    fig.add_trace(
        go.Scatter(
            x=[depot_x],
            y=[depot_y],
            mode="markers+text",
            marker=dict(size=16, symbol="diamond"),
            text=["DEPOT"],
            textposition="bottom center",
            name="Depot",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Aisle Position",
        yaxis_title="Rack Position",
        height=720,
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )

    fig.update_xaxes(range=[-2, max(aisle_xs) + 2])
    fig.update_yaxes(range=[-8, 94], scaleanchor="x", scaleratio=1)

    return fig