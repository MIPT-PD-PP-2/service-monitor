import asyncio
import aiohttp
import time
import threading
from datetime import datetime
from pathlib import Path

BASE_URL = "http://localhost:8000"
TEST_DURATION_SECONDS = 600
CHECK_INTERVAL_SECONDS = 60
NUM_SERVICES = 50
SLA_TARGET_MS = 500

async def create_service(session, name: str):
    async with session.post(f"{BASE_URL}/services", json={"name": name}) as resp:
        if resp.status in (200, 201):
            return await resp.json()
        else:
            print(f"Failed to create service {name}: {resp.status} - {await resp.text()}")
            return None

async def add_endpoint(session, service_id: int, url: str):
    payload = {"url": url, "method": "GET"}
    async with session.post(f"{BASE_URL}/services/{service_id}/endpoints", json=payload) as resp:
        return resp.status in (200, 201)

async def trigger_checks(session):
    async with session.post(f"{BASE_URL}/monitoring/trigger") as resp:
        return await resp.json()

async def sla_test(session, service_id: int):
    start = time.time()
    async with session.get(f"{BASE_URL}/sla/test/{service_id}") as resp:
        data = await resp.json()
    elapsed_ms = int((time.time() - start) * 1000)
    return {
        "query_time_ms": elapsed_ms,
        "within_sla": elapsed_ms < SLA_TARGET_MS,
        "stats": data.get("stats", {})
    }

async def setup_services_and_endpoints():
    async with aiohttp.ClientSession() as session:
        services = []
        for i in range(1, NUM_SERVICES + 1):
            service_name = f"test-service-{i:03d}"
            service = await create_service(session, service_name)
            if service:
                service_id = service["id"]
                if i % 3 == 0:
                    url = "https://httpbin.org/delay/1"
                elif i % 5 == 0:
                    url = "https://httpbin.org/status/500"
                else:
                    url = "https://httpbin.org/get"
                ok = await add_endpoint(session, service_id, url)
                if ok:
                    services.append(service_id)
                else:
                    print(f"Failed to add endpoint for {service_name}")
            await asyncio.sleep(0.1)
        print(f"Created services with endpoints: {len(services)}/{NUM_SERVICES}")
        return services

async def run_check_cycle(session, cycle_num: int):
    start = time.time()
    await trigger_checks(session)
    elapsed = time.time() - start
    print(f"Cycle {cycle_num}: checks triggered in {elapsed:.2f}s")
    return {"cycle": cycle_num, "duration_seconds": elapsed}

async def populate_history(session, service_id: int, target: int = 10100):
    print(f"Creating {target} history records for service {service_id}...")
    current = 0
    while current < target:
        batch = min(10, target - current)
        tasks = [trigger_checks(session) for _ in range(batch)]
        await asyncio.gather(*tasks)
        current += batch
        if current % 1000 == 0:
            print(f"Created {current} records")
        await asyncio.sleep(1)
    print("Done")
    return await sla_test(session, service_id)

def monitor_docker_stats(stop_event, results):
    import docker
    client = docker.from_env()
    container_name = "service-monitor-main-app-1"
    while not stop_event.is_set():
        try:
            c = client.containers.get(container_name)
            s = c.stats(stream=False)
            cpu = 0.0
            if 'cpu_stats' in s and 'precpu_stats' in s:
                cpu_delta = s['cpu_stats']['cpu_usage']['total_usage'] - s['precpu_stats']['cpu_usage']['total_usage']
                sys_delta = s['cpu_stats']['system_cpu_usage'] - s['precpu_stats']['system_cpu_usage']
                if sys_delta > 0:
                    cpu = (cpu_delta / sys_delta) * 100.0
            mem_mb = s['memory_stats']['usage'] / (1024*1024)
            results.append({"timestamp": datetime.now().isoformat(), "cpu": round(cpu,2), "mem": round(mem_mb,2)})
            time.sleep(5)
        except:
            time.sleep(5)

async def run_load_test():
    print("=== LOAD TEST - SCHEDULER ===\n")
    print("1. Creating 50 services with endpoints...")
    services = await setup_services_and_endpoints()
    if not services:
        print("Failed to create services, exiting")
        return
    service_id_for_sla = services[0]

    print("\n2. Preparing SLA test data (10,000+ records)...")
    async with aiohttp.ClientSession() as sess:
        sla_before = await populate_history(sess, service_id_for_sla, 10100)

    print("\n3. Starting Docker resource monitoring...")
    stop_event = threading.Event()
    docker_stats = []
    monitor_thread = threading.Thread(target=monitor_docker_stats, args=(stop_event, docker_stats))
    monitor_thread.start()

    print(f"\n4. Main test for {TEST_DURATION_SECONDS // 60} minutes...")
    cycles = []
    start_time = time.time()
    cycle_num = 0
    async with aiohttp.ClientSession() as sess:
        while time.time() - start_time < TEST_DURATION_SECONDS:
            cycle_num += 1
            cyc_start = time.time()
            res = await run_check_cycle(sess, cycle_num)
            cycles.append(res)
            elapsed = time.time() - cyc_start
            wait = max(0, CHECK_INTERVAL_SECONDS - elapsed)
            if wait > 0 and (time.time() - start_time) < TEST_DURATION_SECONDS:
                print(f"  Waiting {wait:.1f}s until next cycle...")
                await asyncio.sleep(wait)

    print("\n5. Final SLA test...")
    async with aiohttp.ClientSession() as sess:
        sla_after = await sla_test(sess, service_id_for_sla)

    print("\n6. Stopping monitoring...")
    stop_event.set()
    monitor_thread.join()

    async with aiohttp.ClientSession() as sess:
        async with sess.get(f"{BASE_URL}/services") as resp:
            services_list = await resp.json()
            active_services = len(services_list)
    print(f"Active services at the end: {active_services} (expected {NUM_SERVICES})")

    durations = [c["duration_seconds"] for c in cycles]

    if docker_stats:
        avg_cpu = sum(x["cpu"] for x in docker_stats)/len(docker_stats)
        max_cpu = max(x["cpu"] for x in docker_stats)
        avg_mem = sum(x["mem"] for x in docker_stats)/len(docker_stats)
        max_mem = max(x["mem"] for x in docker_stats)
    else:
        avg_cpu = max_cpu = avg_mem = max_mem = 0

    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "performance.md"

    report = f"""# Performance Test Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Results

### 1. Scalability
- Services created: {active_services} / {NUM_SERVICES}
- Check cycles performed: {len(cycles)}
- Check interval: {CHECK_INTERVAL_SECONDS} s
- Test duration: {TEST_DURATION_SECONDS // 60} min

### 2. Cycle duration
- Average: {sum(durations)/len(durations):.2f} s
- Maximum: {max(durations):.2f} s
- Minimum: {min(durations):.2f} s

### 3. Resource consumption (Docker)
- CPU: avg {avg_cpu:.1f}%, max {max_cpu:.1f}%
- RAM: avg {avg_mem:.1f} MB, max {max_mem:.1f} MB

### 4. SLA test (query with 10k+ history)
- Query time: {sla_after['query_time_ms']} ms
- Target: < {SLA_TARGET_MS} ms
- Compliance: {'PASS' if sla_after['within_sla'] else 'FAIL'}

## Conclusion
"""
    if active_services == NUM_SERVICES:
        report += "PASS: All 50 services created and checked.\n"
    else:
        report += f"FAIL: Only {active_services} of {NUM_SERVICES} services created.\n"

    if sla_after['within_sla']:
        report += "PASS: SLA requirement met (< 500 ms).\n"
    else:
        report += f"FAIL: SLA requirement not met ({sla_after['query_time_ms']} ms).\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved: {report_path}")
    print(f"SLA: {sla_after['query_time_ms']} ms - {'PASS' if sla_after['within_sla'] else 'FAIL'}")
    print(f"CPU: {avg_cpu:.1f}%, RAM: {avg_mem:.1f} MB")

if __name__ == "__main__":
    asyncio.run(run_load_test())