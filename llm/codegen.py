import json
import os
import re

OUTPUT_DIR = "generated_app"


def _mkdir(path: str):
    os.makedirs(path, exist_ok=True)


def generate_models(entities: list) -> str:
    """Generate SQLAlchemy models from entity definitions."""
    lines = [
        "from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text",
        "from sqlalchemy.ext.declarative import declarative_base",
        "from datetime import datetime",
        "",
        "Base = declarative_base()",
        "",
    ]

    TYPE_MAP = {
        "string":   "String(255)",
        "str":      "String(255)",
        "int":      "Integer",
        "integer":  "Integer",
        "bool":     "Boolean",
        "boolean":  "Boolean",
        "datetime": "DateTime",
        "text":     "Text",
        "uuid":     "String(36)",
    }

    for entity in entities:
        name   = entity.get("name", "UnknownEntity")
        fields = entity.get("attributes", entity.get("fields", []))

        lines.append(f"class {name}(Base):")
        lines.append(f'    __tablename__ = "{name.lower()}s"')

        # Always ensure a primary key exists
        has_id = any(
            (f.get("name") if isinstance(f, dict) else str(f)) in ("id", "uuid")
            for f in fields
        )
        if not has_id:
            lines.append('    id = Column(Integer, primary_key=True, index=True)')

        for field in fields:
            if isinstance(field, dict):
                fname = field.get("name", "field")
                ftype = field.get("type", "string").lower()
            else:
                fname = str(field)
                ftype = "string"

            is_pk  = fname in ("id", "uuid")
            col_type = TYPE_MAP.get(ftype, "String(255)")

            if is_pk:
                lines.append(f"    {fname} = Column({col_type}, primary_key=True, index=True)")
            elif fname.endswith("_id"):
                # Treat as foreign key — reference to parent table
                ref_table = fname.replace("_id", "") + "s"
                lines.append(f"    {fname} = Column({col_type}, ForeignKey('{ref_table}.id'))")
            else:
                lines.append(f"    {fname} = Column({col_type})")

        lines.append("")

    return "\n".join(lines)


def generate_router(service: dict) -> str:
    """Generate a FastAPI router from a service definition."""
    name      = service.get("name", "Service").replace("Service", "")
    endpoints = service.get("endpoints", [])
    tag       = name.lower()

    lines = [
        "from fastapi import APIRouter, HTTPException",
        "from typing import List, Optional",
        "",
        f'router = APIRouter(prefix="/{tag}", tags=["{name}"])',
        "",
    ]

    METHOD_MAP = {
        "GET":    "get",
        "POST":   "post",
        "PUT":    "put",
        "PATCH":  "patch",
        "DELETE": "delete",
    }

    for ep in endpoints:
        if isinstance(ep, dict):
            method    = ep.get("method", "GET").upper()
            route     = ep.get("route", ep.get("path", "/"))
            ep_name   = ep.get("name", ep.get("summary", "endpoint"))
            auth      = ep.get("authLevel", ep.get("auth", "Public"))
        else:
            method, route, ep_name, auth = "GET", "/", str(ep), "Public"

        # Clean up route — ensure it starts with /
        if not route.startswith("/"):
            route = "/" + route

        decorator    = METHOD_MAP.get(method, "get")
        func_name = ep_name.lower().replace(" ", "_").replace("-", "_").replace("'", "").replace("(", "").replace(")", "").replace("/", "_").replace(".", "_")
        func_name = re.sub(r'[^a-z0-9_]', '', func_name)  # remove any remaining special chars
        func_name = re.sub(r'_+', '_', func_name).strip('_')  # clean up multiple underscores
        if not func_name:
            func_name = "endpoint"
        auth_comment = f"  # auth: {auth}" if auth != "Public" else ""

        lines.append(f'@router.{decorator}("{route}")')
        lines.append(f"async def {func_name}():{auth_comment}")
        lines.append(f'    """{ ep_name }"""')
        lines.append(f"    return {{\"message\": \"{ep_name} endpoint working\"}}")
        lines.append("")

    return "\n".join(lines)


def generate_main(services: list, project_name: str) -> str:
    """Generate the FastAPI main.py entry point."""
    router_imports = []
    router_includes = []

    for svc in services:
        name       = svc.get("name", "Service")
        module   = re.sub(r'[^a-z0-9]', '_', name.lower().replace("service", "").strip()) + "_router"
        module   = re.sub(r'_+', '_', module).strip('_')
        var_name = module
        tag        = name.replace("Service", "").lower()

        router_imports.append(f"from routers.{module} import router as {var_name}")
        router_includes.append(f'app.include_router({var_name}, prefix="/api/v1")')

    lines = [
        "from fastapi import FastAPI",
        "from fastapi.middleware.cors import CORSMiddleware",
        *router_imports,
        "",
        f'app = FastAPI(title="{project_name}", version="1.0.0")',
        "",
        "app.add_middleware(",
        "    CORSMiddleware,",
        '    allow_origins=["*"],',
        "    allow_methods=[\"*\"],",
        "    allow_headers=[\"*\"],",
        ")",
        "",
        *router_includes,
        "",
        '@app.get("/health")',
        "async def health():",
        '    return {"status": "ok"}',
        "",
        'if __name__ == "__main__":',
        "    import uvicorn",
        '    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)',
    ]

    return "\n".join(lines)


def generate_requirements() -> str:
    return "\n".join([
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "python-jose>=3.3.0",
        "passlib>=1.7.4",
        "python-multipart>=0.0.9",
    ])


def run_codegen(pipeline_json_path: str = "final_output.json"):
    print("\n--- CODEGEN: Generating runnable FastAPI app ---")

    with open(pipeline_json_path, "r") as f:
        pipeline = json.load(f)

    architecture = pipeline.get("architecture", {})
    app_design   = pipeline.get("app_design", {})

    services     = architecture.get("services", [])
    entities     = app_design.get("entities", architecture.get("entities", []))
    project_name = architecture.get("project_name", "GeneratedApp")

    # ── Merge endpoints from app_design into each service ──
    # ── Merge endpoints from app_design into each service ──
    # Handle both dict format {"/path": "ServiceName"} and list format
    raw_api_endpoints = app_design.get("api_endpoints", {})
    api_config        = app_design.get("api_config", {})
    api_endpoints_mapped = app_design.get("api_endpoints_mapped", {})

    # Build service → list of routes from the dict format
    service_routes = {}  # {"UserService": ["/user", "/user/*"], ...}

    # From api_endpoints (dict)
    if isinstance(raw_api_endpoints, dict):
        for path, svc_name in raw_api_endpoints.items():
            if isinstance(svc_name, str):
                service_routes.setdefault(svc_name, []).append(path)

    # From api_endpoints_mapped (dict) — more specific paths
    if isinstance(api_endpoints_mapped, dict):
        for path, svc_name in api_endpoints_mapped.items():
            if isinstance(svc_name, str):
                service_routes.setdefault(svc_name, []).append(path)

    # From api_config.api_endpoints (dict)
    cfg_endpoints = api_config.get("api_endpoints", {})
    if isinstance(cfg_endpoints, dict):
        for path, svc_name in cfg_endpoints.items():
            if isinstance(svc_name, str):
                service_routes.setdefault(svc_name, []).append(path)

    # Now inject endpoints into each service
    for svc in services:
        svc_name = svc.get("name", "")
        routes   = service_routes.get(svc_name, [])

        if routes:
            seen = set()
            merged = []
            for route in routes:
                clean_route = route.rstrip("*")  # remove trailing wildcard
                if not clean_route.startswith("/"):
                    clean_route = "/" + clean_route

                # Generate standard CRUD endpoints for each base route
                for method, suffix, label in [
                    ("GET",    "",       f"get_{svc_name.lower()}"),
                    ("POST",   "",       f"create_{svc_name.lower()}"),
                    ("PUT",    "/{id}",  f"update_{svc_name.lower()}"),
                    ("DELETE", "/{id}",  f"delete_{svc_name.lower()}"),
                ]:
                    full_route = clean_route + suffix
                    key = f"{method}:{full_route}"
                    if key not in seen:
                        seen.add(key)
                        merged.append({
                            "method":    method,
                            "route":     full_route,
                            "name":      label,
                            "authLevel": "Authenticated"
                        })

            svc["endpoints"] = merged

    # Create output directories
    routers_dir = os.path.join(OUTPUT_DIR, "routers")
    _mkdir(OUTPUT_DIR)
    _mkdir(routers_dir)

    # 1. models.py
    models_code = generate_models(entities)
    with open(os.path.join(OUTPUT_DIR, "models.py"), "w") as f:
        f.write(models_code)
    print(f"  ✅ models.py — {len(entities)} entities")

    # 2. One router per service
    for svc in services:
        name        = svc.get("name", "Service")
        module_name = re.sub(r'[^a-z0-9]', '_', name.lower().replace("service", "").strip()) + "_router"
        module_name = re.sub(r'_+', '_', module_name).strip('_')
        router_code = generate_router(svc)
        router_path = os.path.join(routers_dir, f"{module_name}.py")
        with open(router_path, "w") as f:
            f.write(router_code)
        print(f"  ✅ routers/{module_name}.py — {len(svc.get('endpoints', []))} endpoints")

    # 3. routers/__init__.py
    with open(os.path.join(routers_dir, "__init__.py"), "w") as f:
        f.write("")

    # 4. main.py
    main_code = generate_main(services, project_name)
    with open(os.path.join(OUTPUT_DIR, "main.py"), "w") as f:
        f.write(main_code)
    print(f"  ✅ main.py — {len(services)} routers registered")

    # 5. requirements.txt
    with open(os.path.join(OUTPUT_DIR, "requirements.txt"), "w") as f:
        f.write(generate_requirements())
    print("  ✅ requirements.txt")

    print(f"\n✅ App generated in ./{OUTPUT_DIR}/")
    print("   To run it:")
    print(f"   cd {OUTPUT_DIR} && pip install -r requirements.txt && python main.py")