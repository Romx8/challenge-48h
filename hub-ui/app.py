from __future__ import annotations

import os
import time
from datetime import datetime

import altair as alt
import docker
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="Unified Platform", layout="wide")

SERVICES = {
    "hub-ui": {"label": "Central UI", "url": os.getenv("HUB_UI_URL", "http://localhost:8501")},
    "frontend": {"label": "Dev Frontend", "url": os.getenv("FRONTEND_URL", "http://localhost:5173")},
    "backend": {"label": "Dev Backend", "url": os.getenv("BACKEND_URL", "http://localhost:8787")},
    "data-api": {"label": "Data API", "url": os.getenv("DATA_API_URL", "http://localhost:8000")},
    "prometheus": {"label": "Prometheus", "url": os.getenv("PROMETHEUS_URL", "http://localhost:9090")},
    "grafana": {"label": "Grafana", "url": os.getenv("GRAFANA_URL", "http://localhost:3000")},
    "blackbox": {"label": "Blackbox", "url": os.getenv("BLACKBOX_URL", "http://localhost:9115")},
    "docker-exporter": {"label": "Docker Exporter", "url": os.getenv("DOCKER_EXPORTER_URL", "http://localhost:9324")},
    "postgres": {"label": "PostgreSQL", "url": "n/a"},
    "cadvisor": {"label": "cAdvisor", "url": os.getenv("CADVISOR_URL", "http://localhost:8080")},
}
PROMETHEUS_INTERNAL_URL = os.getenv("PROMETHEUS_INTERNAL_URL", "http://prometheus:9090").rstrip("/")
MANAGED_SERVICES = [name for name in SERVICES.keys() if name != "hub-ui"]


@st.cache_resource
def get_docker_client() -> docker.DockerClient | None:
    try:
        return docker.from_env()
    except Exception:
        return None


def get_container_statuses(client: docker.DockerClient | None) -> dict[str, dict[str, str]]:
    statuses: dict[str, dict[str, str]] = {}
    for service_name in SERVICES:
        statuses[service_name] = {"state": "unknown", "status": "not found"}

    if client is None:
        return statuses

    try:
        containers = client.containers.list(all=True)
    except Exception:
        return statuses

    for container in containers:
        raw_name = container.name
        if raw_name in statuses:
            statuses[raw_name] = {
                "state": container.attrs.get("State", {}).get("Status", "unknown"),
                "status": container.status,
            }

    return statuses


def _bulk_service_action(client: docker.DockerClient | None, action: str) -> tuple[list[str], list[str]]:
    if client is None:
        return [], ["Docker socket indisponible dans le container hub-ui."]

    ok: list[str] = []
    errors: list[str] = []

    for service_name in MANAGED_SERVICES:
        try:
            container = client.containers.get(service_name)
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop(timeout=20)
            elif action == "restart":
                container.restart(timeout=20)
            else:
                errors.append(f"Action inconnue: {action}")
                continue
            ok.append(service_name)
        except Exception as exc:
            errors.append(f"{service_name}: {exc}")

    return ok, errors


def _service_action(client: docker.DockerClient | None, service_name: str, action: str) -> str:
    if client is None:
        return "Docker socket indisponible dans le container hub-ui."
    try:
        container = client.containers.get(service_name)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop(timeout=20)
        elif action == "restart":
            container.restart(timeout=20)
        else:
            return f"Action inconnue: {action}"
        return ""
    except Exception as exc:
        return str(exc)


def _extract_container_details(container: docker.models.containers.Container) -> dict[str, str]:
    attrs = container.attrs
    state = attrs.get("State", {})
    health = state.get("Health", {}).get("Status", "n/a")
    started_at = state.get("StartedAt", "n/a")
    image = attrs.get("Config", {}).get("Image", "n/a")
    ports_raw = attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
    port_rows: list[str] = []
    for container_port, host_bindings in ports_raw.items():
        if not host_bindings:
            port_rows.append(container_port)
            continue
        for binding in host_bindings:
            host_port = binding.get("HostPort", "?")
            host_ip = binding.get("HostIp", "0.0.0.0")
            port_rows.append(f"{host_ip}:{host_port}->{container_port}")
    ports = ", ".join(port_rows) if port_rows else "n/a"
    return {
        "image": image,
        "health": health,
        "started_at": started_at,
        "ports": ports,
    }


def _build_flow_chart() -> alt.Chart:
    nodes = [
        {"id": "data_gouv", "label": "data.gouv.fr", "type": "source", "x": 0, "y": 6, "endpoint": "opendata"},
        {"id": "geodair", "label": "GeoD'Air", "type": "source", "x": 0, "y": 2, "endpoint": "api-ext"},
        {"id": "data_api", "label": "data-api", "type": "service", "x": 28, "y": 4, "endpoint": "GET /api/v1/index/history"},
        {"id": "backend", "label": "backend", "type": "service", "x": 54, "y": 4, "endpoint": "GET /api/v1/readings"},
        {"id": "postgres", "label": "postgres", "type": "storage", "x": 54, "y": 0, "endpoint": "read/write"},
        {"id": "frontend", "label": "frontend", "type": "ui", "x": 80, "y": 4, "endpoint": "carte + filtres"},
        {"id": "hub", "label": "hub-ui", "type": "ui", "x": 80, "y": 8, "endpoint": "vue centralisee"},
        {"id": "prom", "label": "prometheus", "type": "monitoring", "x": 54, "y": 8, "endpoint": "scrape"},
        {"id": "blackbox", "label": "blackbox", "type": "monitoring", "x": 40, "y": 10, "endpoint": "probe"},
        {"id": "docker_exp", "label": "docker-exporter", "type": "monitoring", "x": 40, "y": 8, "endpoint": "docker metrics"},
        {"id": "grafana", "label": "grafana", "type": "monitoring", "x": 80, "y": 10, "endpoint": "dashboards"},
    ]
    edges = [
        {"source": "data_gouv", "target": "data_api", "flow": "pollution"},
        {"source": "geodair", "target": "data_api", "flow": "meteo"},
        {"source": "data_api", "target": "backend", "flow": "indice agrege"},
        {"source": "backend", "target": "postgres", "flow": "upsert/cache"},
        {"source": "backend", "target": "frontend", "flow": "readings filtres"},
        {"source": "hub", "target": "frontend", "flow": "navigation"},
        {"source": "blackbox", "target": "prom", "flow": "probe metrics"},
        {"source": "docker_exp", "target": "prom", "flow": "container metrics"},
        {"source": "prom", "target": "backend", "flow": "scrape /metrics"},
        {"source": "prom", "target": "grafana", "flow": "datasource"},
        {"source": "hub", "target": "prom", "flow": "observabilite"},
        {"source": "hub", "target": "grafana", "flow": "dashboards"},
    ]

    nodes_df = pd.DataFrame(nodes)
    node_coords = {n["id"]: (n["x"], n["y"]) for n in nodes}

    edge_points: list[dict[str, object]] = []
    for idx, edge in enumerate(edges):
        sx, sy = node_coords[edge["source"]]
        tx, ty = node_coords[edge["target"]]
        edge_points.append({"edge": idx, "x": sx, "y": sy, "flow": edge["flow"]})
        edge_points.append({"edge": idx, "x": tx, "y": ty, "flow": edge["flow"]})
    edges_df = pd.DataFrame(edge_points)

    line_layer = (
        alt.Chart(edges_df)
        .mark_line(strokeWidth=2.2, color="#7f8ea3", opacity=0.75)
        .encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-5, 90])),
            y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1, 12])),
            detail="edge:N",
            tooltip=[alt.Tooltip("flow:N", title="Flux")],
        )
    )

    point_layer = (
        alt.Chart(nodes_df)
        .mark_circle(size=1200, opacity=0.95)
        .encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-5, 90])),
            y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1, 12])),
            color=alt.Color("type:N", legend=alt.Legend(title="Type")),
            tooltip=[
                alt.Tooltip("label:N", title="Noeud"),
                alt.Tooltip("type:N", title="Type"),
                alt.Tooltip("endpoint:N", title="Usage"),
            ],
        )
    )

    text_layer = (
        alt.Chart(nodes_df)
        .mark_text(fontSize=12, fontWeight="bold", dy=-18)
        .encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-5, 90])),
            y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1, 12])),
            text="label:N",
        )
    )

    return (line_layer + point_layer + text_layer).properties(height=440).interactive()


def show_overview() -> None:
    st.subheader("Plateforme unifiee")
    st.write(
        "Interface centralisee pour naviguer entre dev/data/infra, observer l'etat des services "
        "et consulter monitoring/API en un seul point."
    )

    client = get_docker_client()
    statuses = get_container_statuses(client)

    cols = st.columns(4)
    for idx, (name, meta) in enumerate(SERVICES.items()):
        state = statuses[name]["state"]
        status = statuses[name]["status"]
        indicator = "UP" if status == "running" else "DOWN"
        with cols[idx % 4]:
            st.markdown(f"**{meta['label']}**")
            st.caption(f"service: `{name}`")
            st.caption(f"status: `{indicator}`")
            st.caption(f"state: `{state}`")

    st.markdown("### Schema des flux (interactif)")
    st.caption("Visualisation fonctionnelle/fictive du flux de donnees, incluant data.gouv.fr et GeoD'Air.")
    st.altair_chart(_build_flow_chart(), use_container_width=True)

    st.markdown("### Endpoints principaux")
    st.table(
        [
            {"Service": "backend", "Endpoint": "GET /api/v1/readings", "Usage": "carte + filtres"},
            {"Service": "backend", "Endpoint": "POST /api/v1/jobs/sync", "Usage": "sync manuelle"},
            {"Service": "data-api", "Endpoint": "GET /api/v1/index/history", "Usage": "source data"},
            {"Service": "data-api", "Endpoint": "POST /api/v1/jobs/refresh", "Usage": "recalcul indice"},
            {"Service": "backend", "Endpoint": "GET /metrics", "Usage": "prometheus scrape"},
        ]
    )


def show_containers() -> None:
    st.subheader("Containers")
    client = get_docker_client()

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        start_all = st.button("Demarrer la stack (hors hub-ui)", use_container_width=True)
    with action_col2:
        stop_all = st.button("Arreter la stack (hors hub-ui)", use_container_width=True)
    with action_col3:
        restart_all = st.button("Redemarrer la stack (hors hub-ui)", use_container_width=True)

    if start_all:
        ok, errors = _bulk_service_action(client, "start")
        st.success(f"Services demarres: {', '.join(ok)}" if ok else "Aucun service demarre")
        for err in errors:
            st.error(err)
    if stop_all:
        ok, errors = _bulk_service_action(client, "stop")
        st.warning(f"Services arretes: {', '.join(ok)}" if ok else "Aucun service arrete")
        for err in errors:
            st.error(err)
    if restart_all:
        ok, errors = _bulk_service_action(client, "restart")
        st.info(f"Services redemarres: {', '.join(ok)}" if ok else "Aucun service redemarre")
        for err in errors:
            st.error(err)

    if client is None:
        st.error("Docker socket indisponible dans le container hub-ui.")
        return

    statuses = get_container_statuses(client)
    tail = st.slider("Dernieres lignes de logs", min_value=20, max_value=500, value=120, step=20)
    live_logs = st.toggle("Logs en temps reel", value=False)
    refresh_seconds = st.slider("Intervalle logs (sec)", min_value=2, max_value=20, value=5, step=1)

    st.markdown("### Detail par service")
    for name, meta in SERVICES.items():
        state = statuses[name]["state"]
        status = statuses[name]["status"]
        indicator = "UP" if status == "running" else "DOWN"
        with st.expander(f"{meta['label']} ({name}) - {indicator}", expanded=False):
            container = None
            try:
                container = client.containers.get(name)
            except Exception:
                container = None

            if container is not None:
                details = _extract_container_details(container)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.caption(f"status: `{indicator}`")
                    st.caption(f"state: `{state}`")
                    st.caption(f"health: `{details['health']}`")
                with c2:
                    st.caption(f"image: `{details['image']}`")
                    st.caption(f"started_at: `{details['started_at']}`")
                with c3:
                    st.caption(f"ports: `{details['ports']}`")
                    if meta["url"] != "n/a":
                        st.markdown(f"[Ouvrir service]({meta['url']})")
            else:
                st.warning("Container non trouve dans Docker.")

            if name == "hub-ui":
                st.info("Actions Start/Stop desactivees pour hub-ui afin de garder l'interface disponible.")
            else:
                a1, a2, a3 = st.columns(3)
                with a1:
                    if st.button("Start", key=f"start_{name}", use_container_width=True):
                        err = _service_action(client, name, "start")
                        if err:
                            st.error(err)
                        else:
                            st.success(f"{name} demarre")
                            st.rerun()
                with a2:
                    if st.button("Stop", key=f"stop_{name}", use_container_width=True):
                        err = _service_action(client, name, "stop")
                        if err:
                            st.error(err)
                        else:
                            st.warning(f"{name} arrete")
                            st.rerun()
                with a3:
                    if st.button("Restart", key=f"restart_{name}", use_container_width=True):
                        err = _service_action(client, name, "restart")
                        if err:
                            st.error(err)
                        else:
                            st.info(f"{name} redemarre")
                            st.rerun()

            st.markdown("**Logs**")
            if container is None:
                st.code("(pas de logs: container absent)")
            else:
                try:
                    logs = container.logs(tail=tail).decode("utf-8", errors="replace")
                    st.code(logs or "(pas de logs)")
                except Exception as exc:
                    st.error(f"Impossible de lire les logs: {exc}")

    if live_logs:
        time.sleep(refresh_seconds)
        st.rerun()


def show_data_page() -> None:
    st.subheader("Data API")
    base_url = SERVICES["data-api"]["url"]
    docs_mode = st.radio("Vue", ["Swagger", "ReDoc", "Health"], horizontal=True)

    if docs_mode == "Swagger":
        st.write(f"URL: `{base_url}/docs`")
        components.iframe(f"{base_url}/docs", height=820, scrolling=True)
    elif docs_mode == "ReDoc":
        st.write(f"URL: `{base_url}/redoc`")
        components.iframe(f"{base_url}/redoc", height=820, scrolling=True)
    else:
        st.write(f"URL: `{base_url}/health`")
        components.iframe(f"{base_url}/health", height=180, scrolling=True)


def _prom_query(expr: str) -> tuple[list[dict], str | None]:
    try:
        response = requests.get(
            f"{PROMETHEUS_INTERNAL_URL}/api/v1/query",
            params={"query": expr},
            timeout=4,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return [], f"Reponse Prometheus invalide: {payload}"
        return payload.get("data", {}).get("result", []), None
    except Exception as exc:
        return [], str(exc)


def _prom_targets() -> tuple[list[dict], str | None]:
    try:
        response = requests.get(f"{PROMETHEUS_INTERNAL_URL}/api/v1/targets", timeout=4)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return [], f"Reponse Prometheus invalide: {payload}"
        return payload.get("data", {}).get("activeTargets", []), None
    except Exception as exc:
        return [], str(exc)


def show_monitoring_page() -> None:
    st.subheader("Monitoring")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Grafana**")
        st.write(f"{SERVICES['grafana']['url']}")
        components.iframe(SERVICES["grafana"]["url"], height=760, scrolling=True)

    with col2:
        st.markdown("**Prometheus**")
        st.write(f"{SERVICES['prometheus']['url']}")
        st.caption(f"API interne: `{PROMETHEUS_INTERNAL_URL}`")
        st.markdown(
            f"[Ouvrir Prometheus (up par defaut)]({SERVICES['prometheus']['url']}/graph?g0.expr=up&g0.tab=0)"
        )
        st.markdown(f"[Ouvrir Prometheus Home]({SERVICES['prometheus']['url']})")
        st.markdown(f"[Ouvrir Targets]({SERVICES['prometheus']['url']}/targets)")
        st.markdown(f"[Graph `up`]({SERVICES['prometheus']['url']}/graph?g0.expr=up&g0.tab=0)")
        st.markdown(
            f"[Graph `probe_success`]({SERVICES['prometheus']['url']}/graph?g0.expr=probe_success&g0.tab=0)"
        )
        st.markdown(
            f"[Graph CPU services]({SERVICES['prometheus']['url']}/graph?g0.expr=avg%20by%20(service)%20(docker_service_cpu_percent)&g0.tab=0)"
        )
        st.markdown(
            f"[Graph RAM services]({SERVICES['prometheus']['url']}/graph?g0.expr=sum%20by%20(service)%20(docker_service_memory_bytes)&g0.tab=0)"
        )

        up_result, up_error = _prom_query("sum by (job) (up)")
        probe_result, probe_error = _prom_query("max by (service) (probe_success)")
        targets, targets_error = _prom_targets()

        if up_error or probe_error or targets_error:
            st.error(
                "Prometheus joignable en UI mais erreur API interne: "
                f"{up_error or probe_error or targets_error}"
            )
            return

        up_rows: list[dict[str, str]] = []
        for item in up_result:
            metric = item.get("metric", {})
            value = item.get("value", [None, "0"])
            up_rows.append({"job": metric.get("job", "?"), "up_targets": value[1]})

        probe_rows: list[dict[str, str]] = []
        for item in probe_result:
            metric = item.get("metric", {})
            value = item.get("value", [None, "0"])
            probe_rows.append({"service": metric.get("service", "?"), "probe_success": value[1]})

        target_rows: list[dict[str, str]] = []
        for item in targets:
            labels = item.get("labels", {})
            target_rows.append(
                {
                    "job": labels.get("job", "-"),
                    "service": labels.get("service", "-"),
                    "instance": labels.get("instance", "-"),
                    "health": item.get("health", "-"),
                    "last_error": item.get("lastError", ""),
                }
            )

        st.markdown("**Jobs scrape (`up`)**")
        st.table(up_rows)
        st.markdown("**Disponibilite probes (`probe_success`)**")
        st.table(probe_rows)
        st.markdown("**Targets actifs**")
        st.dataframe(target_rows, use_container_width=True, hide_index=True)
        st.markdown(f"[Blackbox UI]({SERVICES['blackbox']['url']})")


def show_dev_page() -> None:
    st.subheader("Dev Webapp")
    st.write(f"{SERVICES['frontend']['url']}")
    components.iframe(SERVICES["frontend"]["url"], height=860, scrolling=True)


st.title("Unified Dev/Data/Infra Platform")
st.caption(f"Dernier rendu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

nav_col, auto_col, interval_col = st.columns([6, 1.5, 2])
with nav_col:
    page = st.radio(
        "Navigation",
        ["Dashboard", "Containers", "Data API", "Monitoring", "Dev App"],
        horizontal=True,
        label_visibility="collapsed",
    )
with auto_col:
    auto_refresh = st.toggle("Auto-refresh", value=False)
with interval_col:
    refresh_seconds = st.slider("Intervalle (sec)", 5, 60, 15)

if page == "Dashboard":
    show_overview()
elif page == "Containers":
    show_containers()
elif page == "Data API":
    show_data_page()
elif page == "Monitoring":
    show_monitoring_page()
else:
    show_dev_page()

if auto_refresh and page != "Containers":
    time.sleep(refresh_seconds)
    st.rerun()
