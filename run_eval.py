import requests
import time
import sys

BASE_URL = "http://localhost:8000"

print("=== PHASE 6: API PROOF ===")
try:
    resp = requests.get(f"{BASE_URL}/health")
    print(f"GET /health -> {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print("\n=== PHASE 7: CSV PROCESSING PROOF ===")
try:
    with open("transactions.csv", "rb") as f:
        files = {"file": ("transactions.csv", f, "text/csv")}
        resp = requests.post(f"{BASE_URL}/jobs/upload", files=files)
        
    print(f"POST /jobs/upload -> {resp.status_code}")
    upload_data = resp.json()
    print(upload_data)
    job_id = upload_data.get("job_id")
    if not job_id:
        print("Failed to get job_id")
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print("\n=== PHASE 9: STATUS POLLING ===")
status = "pending"
while status not in ["completed", "failed"]:
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}/status")
    status_data = resp.json()
    status = status_data.get("status")
    print(f"GET /jobs/{job_id}/status -> {status}")
    if status not in ["completed", "failed"]:
        time.sleep(2)

print("\n=== PHASE 10: RESULTS PROOF ===")
resp = requests.get(f"{BASE_URL}/jobs/{job_id}/results")
results_data = resp.json()
print("Cleaned row count:", results_data.get("job", {}).get("row_count_clean"))
print("Anomaly count:", len(results_data.get("anomalies", [])))
print("Category breakdown:", results_data.get("category_breakdown"))
print("Summary:", results_data.get("summary"))
