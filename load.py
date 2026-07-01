import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

URL = "https://k8s.popnpicks.com/admin"
DURATION = 60  # Run for 60 seconds to allow metrics to collect
CONCURRENCY = 20  # Number of concurrent threads to generate high load

def ensure_localhost(url):
    host = urlparse(url).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("This script only allows localhost URLs.")

def send_request(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            response.read()
            return response.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERROR"

def worker(url, stop_time):
    success = 0
    errors = 0
    while time.perf_counter() < stop_time:
        status = send_request(url)
        if status == 200:
            success += 1
        else:
            errors += 1
        time.sleep(0.001)  # small pause to yield execution
    return success, errors

def main():
    # ensure_localhost(URL)
    
    print(f"Generating load on {URL} for {DURATION} seconds with concurrency {CONCURRENCY}...")
    
    start_time = time.perf_counter()
    stop_time = start_time + DURATION
    
    # Run workers in ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(worker, URL, stop_time) for _ in range(CONCURRENCY)]
        results = [f.result() for f in futures]
        
    total_success = sum(success for success, _ in results)
    total_errors = sum(errors for _, errors in results)
    actual_duration = time.perf_counter() - start_time
    total_requests = total_success + total_errors
    
    print(f"\n--- Load Test Finished ---")
    print(f"Total requests: {total_requests}")
    print(f"Duration: {actual_duration:.2f}s")
    print(f"Requests/sec: {total_requests / actual_duration:.2f}")
    print(f"200 OK: {total_success}")
    print(f"Errors: {total_errors}")

if __name__ == "__main__":
    main()