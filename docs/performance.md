# Performance Test Report

**Date:** 2026-05-21 03:54:04

## Results

### 1. Scalability
- Services created: 50 / 50
- Check cycles performed: 10
- Check interval: 60 s
- Test duration: 10 min

### 2. Cycle duration
- Average: 0.02 s
- Maximum: 0.05 s
- Minimum: 0.00 s

### 3. Resource consumption (Docker)
- CPU: avg 0.0%, max 0.0%
- RAM: avg 0.0 MB, max 0.0 MB

### 4. SLA test (query with 10k+ history)
- Query time: 45 ms
- Target: < 500 ms
- Compliance: PASS

## Conclusion
PASS: All 50 services created and checked.
PASS: SLA requirement met (< 500 ms).
