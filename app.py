import os
import sys
import pandas as pd
import streamlit as st

sys.path.append(os.path.abspath("src"))

import utils
from web_helpers import (
    generate_demo_instance,
    get_all_scenarios,
    parse_scenario_name,
)
from web_visualization import create_warehouse_figure


st.set_page_config(
    page_title="DEPSO Warehouse Optimization",
    page_icon="📦",
    layout="wide",
)

st.title("📦 DEPSO Warehouse Optimization")
st.caption("Order Batching + Picker Routing | Corridor-Safe Route Visualization")

st.sidebar.header("Scenario Settings")

scenario = st.sidebar.selectbox(
    "Scenario",
    get_all_scenarios(),
    index=get_all_scenarios().index("100_2_6")
)

num_orders, max_ol, max_parts = parse_scenario_name(scenario)

seed = st.sidebar.number_input(
    "Random Seed",
    min_value=1,
    max_value=9999,
    value=42,
    step=1
)

st.sidebar.divider()

num_particles = st.sidebar.slider(
    "Particles",
    min_value=5,
    max_value=15,
    value=8,
    step=1
)

max_iterations = st.sidebar.slider(
    "Iterations",
    min_value=50,
    max_value=500,
    value=150,
    step=50
)

run_button = st.sidebar.button("Run DEPSO Demo", type="primary")

tab_overview, tab_run, tab_route, tab_benchmark = st.tabs(
    [
        "Overview",
        "Run Results",
        "Warehouse Route",
        "Benchmark Dashboard",
    ]
)


with tab_overview:
    st.subheader("Project Scope")

    st.write(
        """
        This web application demonstrates the DEPSO algorithm for warehouse
        order batching and picker routing.

        The live demo runs a single scenario instance and visualizes the picker route
        inside the warehouse layout. The route drawing is corridor-safe: the picker
        moves only through picking aisles and cross aisles, never directly over storage racks.
        """
    )

    st.info(
        """
        Recommended demo scenario: 100_2_6 with seed 42.
        For faster live demonstration, use 100–150 iterations.
        """
    )

    st.markdown(
        """
        **Scenario format:** `NOrd_NmaxOl_AmaxOl`

        - `NOrd`: number of orders
        - `NmaxOl`: maximum orderlines per order
        - `AmaxOl`: maximum parts per orderline
        """
    )


with tab_run:
    st.subheader("Live DEPSO Demo")

    st.write(f"Selected scenario: **{scenario}**")
    st.write(
        f"Orders: **{num_orders}**, "
        f"Max orderlines/order: **{max_ol}**, "
        f"Max parts/orderline: **{max_parts}**"
    )

    if run_button:
        with st.spinner("Generating instance and running DEPSO..."):
            orders = generate_demo_instance(
                num_orders=num_orders,
                max_ol=max_ol,
                max_parts_ol=max_parts,
                seed=int(seed),
            )

            batches, routes, depso_distance, convergence = utils.run_depso(
                orders=orders,
                num_particles=num_particles,
                max_iterations=max_iterations,
                threshold_gbest=0.5,
                max_ls_iter=100,
                max_stagnation=20,
                v_p=0.5,
            )

            sop_distance = utils.calculate_sop_distance(
                orders,
                utils.locations_cache,
            )

            fcfs_distance = utils.calculate_fcfs_distance(
                orders,
                utils.locations_cache,
            )

            savings_distance = utils.calculate_savings_distance(
                orders,
                utils.locations_cache,
            )

            st.session_state["orders"] = orders
            st.session_state["batches"] = batches
            st.session_state["routes"] = routes
            st.session_state["depso_distance"] = depso_distance
            st.session_state["sop_distance"] = sop_distance
            st.session_state["fcfs_distance"] = fcfs_distance
            st.session_state["savings_distance"] = savings_distance
            st.session_state["convergence"] = convergence
            st.session_state["scenario"] = scenario

    if "depso_distance" in st.session_state:
        depso = st.session_state["depso_distance"]
        sop = st.session_state["sop_distance"]
        fcfs = st.session_state["fcfs_distance"]
        savings = st.session_state["savings_distance"]

        gap_sop = ((depso - sop) / sop) * 100
        gap_fcfs = ((depso - fcfs) / fcfs) * 100
        gap_savings = ((depso - savings) / savings) * 100

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("DEPSO Distance", f"{depso:.2f} LU")
        col2.metric("SOP Distance", f"{sop:.2f} LU", f"{gap_sop:.2f}%")
        col3.metric("FCFS Distance", f"{fcfs:.2f} LU", f"{gap_fcfs:.2f}%")
        col4.metric("Savings Distance", f"{savings:.2f} LU", f"{gap_savings:.2f}%")

        col_a, col_b = st.columns(2)

        with col_a:
            st.metric("Number of Batches", len(st.session_state["batches"]))

        with col_b:
            max_batch_weight = max(
                sum(utils.get_order_weight(order) for order in batch)
                for batch in st.session_state["batches"]
            )
            st.metric("Max Batch Weight", f"{max_batch_weight:.2f} WU")

        st.subheader("Convergence Curve")
        st.line_chart(st.session_state["convergence"])

    else:
        st.info("Click **Run DEPSO Demo** from the sidebar to start.")


with tab_route:
    st.subheader("Corridor-Safe Warehouse Route Visualization")

    if "routes" not in st.session_state:
        st.info("Run a DEPSO demo first.")
    else:
        batches = st.session_state["batches"]
        routes = st.session_state["routes"]

        selected_batch_index = st.selectbox(
            "Select Batch",
            list(range(len(routes))),
            format_func=lambda i: f"Batch {i + 1} | Orders: {len(batches[i])}",
        )

        selected_batch = batches[selected_batch_index]
        selected_route = routes[selected_batch_index]

        batch_weight = sum(
            utils.get_order_weight(order)
            for order in selected_batch
        )

        route_distance = utils.calculate_route_distance(selected_route)

        col1, col2, col3 = st.columns(3)
        col1.metric("Selected Batch", f"Batch {selected_batch_index + 1}")
        col2.metric("Batch Weight", f"{batch_weight:.2f} WU")
        col3.metric("Route Distance", f"{route_distance:.2f} LU")

        st.success(
            "Corridor-safe drawing is enabled: the route is projected onto aisles and cross aisles."
        )

        fig = create_warehouse_figure(
            route=selected_route,
            batch=selected_batch,
            title=f"Scenario {st.session_state['scenario']} — Batch {selected_batch_index + 1}",
        )

        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Route node sequence"):
            st.code(selected_route)

        with st.expander("Orders in selected batch"):
            batch_rows = []

            for order in selected_batch:
                batch_rows.append(
                    {
                        "Order ID": order.id,
                        "Weight": round(utils.get_order_weight(order), 2),
                        "Orderlines": len(order.lines),
                    }
                )

            st.dataframe(pd.DataFrame(batch_rows), use_container_width=True)


with tab_benchmark:
    st.subheader("Benchmark Dashboard")

    possible_paths = [
        "data/DEPSO_Full_35_Benchmark_With_Savings.csv",
        "../data/DEPSO_Full_35_Benchmark_With_Savings.csv",
        "DEPSO_Full_35_Benchmark_With_Savings.csv",
    ]

    benchmark_path = None

    for path in possible_paths:
        if os.path.exists(path):
            benchmark_path = path
            break

    if benchmark_path is None:
        st.warning(
            """
            Benchmark CSV not found.

            The live demo still works. To enable the dashboard, place
            `DEPSO_Full_35_Benchmark_With_Savings.csv` inside the `data/` folder.
            """
        )
    else:
        df = pd.read_csv(benchmark_path)

        st.write(f"Loaded benchmark file: `{benchmark_path}`")

        selected_row = df[df["Scenario"] == scenario]

        if selected_row.empty:
            st.warning("Selected scenario was not found in the benchmark CSV.")
        else:
            row = selected_row.iloc[0]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("DEPSO Avg", f"{row['DEPSO_Avg']:.2f} LU")
            col2.metric("SOP Avg", f"{row['SOP_Avg']:.2f} LU")
            col3.metric("FCFS Avg", f"{row['FCFS_Avg']:.2f} LU")
            col4.metric("Savings Avg", f"{row['Savings_Avg']:.2f} LU")

            gap_cols = st.columns(3)
            gap_cols[0].metric("Gap vs SOP", f"{row['Gap_SOP_%']:.2f}%")
            gap_cols[1].metric("Gap vs FCFS", f"{row['Gap_FCFS_%']:.2f}%")
            gap_cols[2].metric("Gap vs Savings", f"{row['Gap_Savings_%']:.2f}%")

        st.subheader("All Scenario Results")
        st.dataframe(df, use_container_width=True)