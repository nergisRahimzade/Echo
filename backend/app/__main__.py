"""Start the API server:  python -m app   (run from backend/)

Listens on 0.0.0.0 and the port in $PORT, as hosts like Render require (they set PORT and
send traffic to it). Locally PORT is usually unset, so it uses 8000.
"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Echo API starting on port {port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
