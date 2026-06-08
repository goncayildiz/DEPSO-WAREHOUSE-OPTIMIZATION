import os
import sys
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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

tab_overview, tab_run, tab_route, tab_benchmark, tab_compare = st.tabs(
    [
        "Overview",
        "Run Results",
        "Warehouse Route",
        "Benchmark Dashboard",
        "Algorithm Comparison"
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
            depso_distance = float(depso_distance)
            sop_distance = float(sop_distance)
            fcfs_distance = float(fcfs_distance)
            savings_distance = float(savings_distance)


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
with tab_compare:
    st.subheader("DEPSO vs PG-DEPSO Algorithm Comparison")

    st.write(
        """
        This section compares the original DEPSO algorithm with the improved
        PG-DEPSO algorithm on the same generated warehouse scenario.

        PG-DEPSO adds a pheromone-guided memory layer to the batch assignment step.
        The routing method, mutation logic, movement operator, local search, and
        benchmark structure remain aligned with the original DEPSO implementation.
        """
    )

    st.info(
        """
        Interpretation of PG vs DEPSO gap:
        - Negative value: PG-DEPSO produced a shorter travel distance.
        - Positive value: standard DEPSO produced a shorter travel distance.
        - Values close to zero indicate near-parity.
        """
    )

    st.warning(
        """
        Running comparison executes both algorithms sequentially.
        For live presentation, use smaller settings first:
        Scenario 50_2_6 or 100_2_6, Particles 5–8, Iterations 50–150.
        """
    )

    compare_button = st.button(
        "Run DEPSO vs PG-DEPSO Comparison",
        type="primary"
    )

    if compare_button:
        with st.spinner("Generating instance and running both algorithms..."):
            orders_cmp = generate_demo_instance(
                num_orders=num_orders,
                max_ol=max_ol,
                max_parts_ol=max_parts,
                seed=int(seed),
            )

            # Run standard DEPSO
            # Reset seed so the DEPSO run is reproducible.
            utils.set_seed(int(seed))

            depso_start = time.time()
            depso_batches, depso_routes, depso_distance, depso_conv = utils.run_depso(
                orders=orders_cmp,
                num_particles=num_particles,
                max_iterations=max_iterations,
                threshold_gbest=0.5,
                max_ls_iter=100,
                max_stagnation=20,
                v_p=0.5,
            )
            depso_runtime = time.time() - depso_start

            # Run PG-DEPSO
            # Reset seed again so the improved algorithm starts from a comparable random state.
            utils.set_seed(int(seed))

            pg_start = time.time()
            pg_batches, pg_routes, pg_distance, pg_conv = utils.run_pg_depso_final(
                orders=orders_cmp,
                num_particles=num_particles,
                max_iterations=max_iterations,
                threshold_gbest=0.5,
                max_ls_iter=100,
                max_stagnation=20,
                v_p=0.5,
            )
            pg_runtime = time.time() - pg_start

            depso_distance = float(depso_distance)
            pg_distance = float(pg_distance)

            st.session_state["cmp_orders"] = orders_cmp

            st.session_state["cmp_depso_batches"] = depso_batches
            st.session_state["cmp_depso_routes"] = depso_routes
            st.session_state["cmp_depso_distance"] = depso_distance
            st.session_state["cmp_depso_conv"] = depso_conv
            st.session_state["cmp_depso_runtime"] = depso_runtime

            st.session_state["cmp_pg_batches"] = pg_batches
            st.session_state["cmp_pg_routes"] = pg_routes
            st.session_state["cmp_pg_distance"] = pg_distance
            st.session_state["cmp_pg_conv"] = pg_conv
            st.session_state["cmp_pg_runtime"] = pg_runtime

            st.session_state["cmp_scenario"] = scenario

    if "cmp_depso_distance" in st.session_state:
        depso_distance = st.session_state["cmp_depso_distance"]
        pg_distance = st.session_state["cmp_pg_distance"]

        depso_runtime = st.session_state["cmp_depso_runtime"]
        pg_runtime = st.session_state["cmp_pg_runtime"]

        pg_gap = ((pg_distance - depso_distance) / depso_distance) * 100

        if pg_distance < depso_distance:
            winner = "PG-DEPSO"
            winner_message = f"PG-DEPSO is better by {abs(pg_gap):.3f}%."
            st.success(winner_message)
        elif pg_distance > depso_distance:
            winner = "DEPSO"
            winner_message = f"DEPSO is better by {abs(pg_gap):.3f}%."
            st.warning(winner_message)
        else:
            winner = "Tie"
            winner_message = "Both algorithms produced the same travel distance."
            st.info(winner_message)

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("DEPSO Distance", f"{depso_distance:.2f} LU")
        col2.metric("PG-DEPSO Distance", f"{pg_distance:.2f} LU")
        col3.metric("PG vs DEPSO Gap", f"{pg_gap:.3f}%")
        col4.metric("Winner", winner)

        runtime_cols = st.columns(2)
        runtime_cols[0].metric("DEPSO Runtime", f"{depso_runtime:.2f} s")
        runtime_cols[1].metric("PG-DEPSO Runtime", f"{pg_runtime:.2f} s")

        st.subheader("Distance Comparison")

        fig_distance = go.Figure()

        fig_distance.add_trace(
            go.Bar(
                x=["DEPSO", "PG-DEPSO"],
                y=[depso_distance, pg_distance],
                text=[f"{depso_distance:.2f}", f"{pg_distance:.2f}"],
                textposition="auto",
            )
        )

        fig_distance.update_layout(
            yaxis_title="Travel Distance (LU)",
            template="plotly_white",
            height=420,
        )

        st.plotly_chart(fig_distance, use_container_width=True)

        st.subheader("Convergence Comparison")

        depso_conv = st.session_state["cmp_depso_conv"]
        pg_conv = st.session_state["cmp_pg_conv"]

        conv_df = pd.DataFrame(
            {
                "DEPSO": pd.Series(depso_conv),
                "PG-DEPSO": pd.Series(pg_conv),
            }
        )

        st.line_chart(conv_df)

        st.subheader("Batch and Route Comparison")

        batch_summary = pd.DataFrame(
            [
                {
                    "Algorithm": "DEPSO",
                    "Batches": len(st.session_state["cmp_depso_batches"]),
                    "Distance": round(depso_distance, 2),
                    "Runtime (s)": round(depso_runtime, 2),
                },
                {
                    "Algorithm": "PG-DEPSO",
                    "Batches": len(st.session_state["cmp_pg_batches"]),
                    "Distance": round(pg_distance, 2),
                    "Runtime (s)": round(pg_runtime, 2),
                },
            ]
        )

        st.dataframe(batch_summary, use_container_width=True)

        st.subheader("Route Viewer for Comparison")

        selected_algorithm = st.radio(
            "Select algorithm route to visualize",
            ["DEPSO", "PG-DEPSO"],
            horizontal=True,
            key="comparison_route_algorithm",
        )

        if selected_algorithm == "DEPSO":
            cmp_batches = st.session_state["cmp_depso_batches"]
            cmp_routes = st.session_state["cmp_depso_routes"]
        else:
            cmp_batches = st.session_state["cmp_pg_batches"]
            cmp_routes = st.session_state["cmp_pg_routes"]

        selected_cmp_batch_index = st.selectbox(
            "Select comparison batch",
            list(range(len(cmp_routes))),
            format_func=lambda i: f"Batch {i + 1} | Orders: {len(cmp_batches[i])}",
            key="comparison_batch_select",
        )

        selected_cmp_batch = cmp_batches[selected_cmp_batch_index]
        selected_cmp_route = cmp_routes[selected_cmp_batch_index]

        cmp_batch_weight = sum(
            utils.get_order_weight(order)
            for order in selected_cmp_batch
        )

        cmp_route_distance = float(
            utils.calculate_route_distance(selected_cmp_route)
        )

        route_cols = st.columns(3)
        route_cols[0].metric("Algorithm", selected_algorithm)
        route_cols[1].metric("Batch Weight", f"{cmp_batch_weight:.2f} WU")
        route_cols[2].metric("Route Distance", f"{cmp_route_distance:.2f} LU")

        st.success(
            "Corridor-safe drawing is enabled for both algorithms."
        )

        cmp_fig = create_warehouse_figure(
            route=selected_cmp_route,
            batch=selected_cmp_batch,
            title=(
                f"{selected_algorithm} | Scenario "
                f"{st.session_state['cmp_scenario']} | "
                f"Batch {selected_cmp_batch_index + 1}"
            ),
        )

        st.plotly_chart(cmp_fig, use_container_width=True)

        with st.expander("Selected comparison route node sequence"):
            st.code(selected_cmp_route)

    else:
        st.info("Click **Run DEPSO vs PG-DEPSO Comparison** to compare both algorithms.")
