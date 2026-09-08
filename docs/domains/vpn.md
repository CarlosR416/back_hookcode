# Domain Specification: VPN Nodes & Public Certificates

* **Module:** `apps.vpn`
* **API Prefix:** `/api/vpn/`
* **Responsibility:** Management of VPN server nodes (WireGuard, OpenVPN, IPsec) and serving node public certificates and keys to clients.

---

## 1. Data Models & Entities

### Model `VpnNode` ([apps/vpn/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/vpn/models.py))
Represents a VPN server gateway or tunnel endpoint:
* **Identification:** `name` (unique identifier, e.g., `"vpn-gateway-01"`), `description` (optional).
* **Network Connectivity:** `host` (public hostname or IP address), `port` (VPN service port, defaults to `51820`), `internal_ip` (internal tunnel IP address, e.g., `10.8.0.1/24`).
* **Protocol / VPN Type:** `vpn_type` (`wireguard`, `openvpn`, `ipsec`).
* **Credentials:** `public_certificate` (Text field containing PEM certificate or WireGuard public key).
* **Operational Status:** `is_active` (boolean, defaults to `True`).

---

## 2. Invariants & Business Rules

1. **Active Node Resolution:**
   - Only active nodes (`is_active = True`) can serve public certificates. Inactive nodes raise errors when queried via the service layer or return `HTTP 404 Not Found` in API lookups for regular users.
2. **Access Control:**
   - Administrative actions (`create`, `update`, `destroy`) require staff status (`IsAdminUser`).
   - Read actions (`list`, `retrieve`) require authenticated users (`IsAuthenticated`).
   - The `certificate` endpoint is publicly accessible (`AllowAny`) to enable automated RouterOS `/tool fetch` downloads without Bearer authentication headers.
3. **Flexible Certificate Formats:**
   - The certificate endpoint returns a standard JSON data envelope by default.
   - For automated client provisioning (such as MikroTik RouterOS scripts or `curl`), appending `?raw=true` or `?download=true` streams the raw certificate/key directly as `text/plain`.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/vpn/nodes/` | `IsAuthenticated` | Lists active VPN nodes (all for staff). |
| `POST` | `/api/vpn/nodes/` | `IsAdminUser` | Registers a new VPN node. |
| `GET` | `/api/vpn/nodes/{id}/` | `IsAuthenticated` | Retrieves VPN node details. |
| `PUT / PATCH` | `/api/vpn/nodes/{id}/` | `IsAdminUser` | Updates VPN node configuration. |
| `DELETE` | `/api/vpn/nodes/{id}/` | `IsAdminUser` | Deletes a VPN node. |
| `GET` | `/api/vpn/nodes/{id}/certificate/` | `AllowAny` | Serves the public certificate of the node (JSON or raw stream via `?raw=true`). |

---

## 4. Service Layer API ([VpnNodeService](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/vpn/services.py))

```python
from apps.vpn.services import VpnNodeService

# 1. Retrieve public certificate by instance, ID, or name
cert = VpnNodeService.get_public_certificate("vpn-gateway-01")

# 2. Retrieve structured connection and certificate details
details = VpnNodeService.get_node_details(node_id=1)
```

---

## 5. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Service Layer** | [apps/vpn/tests/test_services.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/vpn/tests/test_services.py) | Resolution by instance, ID, name; inactive node rejection; empty certificate validation. |
| **API Endpoints** | [apps/vpn/tests/test_api.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/vpn/tests/test_api.py) | Admin node creation, non-admin denial (`HTTP 403`), JSON and raw certificate streaming (`HTTP 200`), active node filtering. |
