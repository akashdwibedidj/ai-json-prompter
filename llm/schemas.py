from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Union

class Endpoint(BaseModel):
    method: str = "GET"
    route: str
    name: str = "endpoint"
    authLevel: str = "Authenticated"

class Entity(BaseModel):
    name: str
    description: str
    attributes: List[str]
    relationships: List[Any]

class Role(BaseModel):
    name: str
    permissions: List[str]
    description: str

class Flow(BaseModel):
    name: str
    steps: List[str]
    actors: List[str]

class Service(BaseModel):
    name: str
    responsibility: str
    depends_on: List[str]
    endpoints: Optional[List[Endpoint]] = []  # ← ADD THIS

# Stage 1 Schema
class IntentSchema(BaseModel):
    intent_name: str
    user_goal: str
    target_audience: str

# Stage 2 Schema
class ArchitectureSchema(BaseModel):
    project_name: str
    architecture_pattern: str
    tech_stack: Dict[str, str]
    services: List[Service]
    api_style: str
    auth_strategy: str
    deployment_target: str
    notes: List[str]
    warnings: List[str]
    is_valid: bool
    failure_reason: Optional[str] = None

# Stage 3 Schema
class AppDesignSchema(BaseModel):
    app_Design_summary: Optional[str] = None
    entities: List[Entity]
    roles: List[Role]
    flows: List[Flow]
    ui_config: Dict[str, Any]
    api_config: Dict[str, Any]
    api_endpoints: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = []  # ← accepts both
    db_schema: Dict[str, Any]
    auth_rules: Dict[str, Any]
    api_geteway: Optional[Dict[str, Any]] = None
    real_time_communication: Optional[Dict[str, Any]] = None














# from pydantic import BaseModel
# from typing import List, Dict, Optional, Any

# class Entity(BaseModel):
#     name: str
#     description: str
#     attributes: List[str]
#     relationships: List[str]  # e.g., ["belongs to User", "has many Orders"]

# class Role(BaseModel):
#     name: str
#     permissions: List[str]
#     description: str

# class Flow(BaseModel):
#     name: str
#     steps: List[str]
#     actors: List[str]

# class Service(BaseModel):
#     name: str
#     responsibility: str
#     depends_on: List[str]


# # Stage 1 Schema
# class IntentSchema(BaseModel):
#     intent_name: str
#     user_goal: str
#     target_audience: str

# # Stage 2 Schema
# class ArchitectureSchema(BaseModel):
#     project_name: str
#     architecture_pattern: str   # e.g., "MVC", "microservices", "monolith"
#     tech_stack: Dict[str, str]  # layer → technology
#     services: List[Service]
#     api_style: str              # "REST" | "GraphQL" | "gRPC"
#     auth_strategy: str          # e.g., "JWT", "OAuth2", "session"
#     deployment_target: str      # e.g., "cloud (AWS)", "VPS", "serverless"
#     notes: List[str]
#     warnings: List[str]         # surfaced conflicts / risks
#     is_valid: bool
#     failure_reason: Optional[str] = None

# # Stage 3 Schema
# class AppDesignSchema(BaseModel):
#     entities: List[Entity]
#     roles: List[Role]
#     flows: List[Flow]
#     ui_config: Dict[str, Any]
#     api_config: Dict[str, Any]
#     api_endpoints: List[Dict[str, Any]]
#     db_schema: Dict[str, Any]
#     auth_rules: Dict[str, Any]
#     api_geteway: Optional[Dict[str, Any]] = None
#     real_time_communication: Optional[Dict[str, Any]] = None
    