@"
import subprocess
import csv
import time
import statistics
from datetime import datetime

TARGET   = "8.8.8.8"
DURATION = 60         # 1 minute
OUTPUT   = "ping_sample.csv"

def ping_once(host):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", host],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "time=" in line or "time<" in line:
                if "time<" in line:
                    return 1.0
                part = line.split("time=")[1].split("ms")[0].strip()
                return float(part)
        return None
    except Exception:
        return None

def remove_outliers(readings):
    """
    Remove outliers using IQR method
    Anything above Q3 + 1.5*IQR is an abnormal spike
    """
    if len(readings) < 4:
        return readings
    sorted_r = sorted(readings)
    q1 = sorted_r[len(sorted_r) // 4]
    q3 = sorted_r[(3 * len(sorted_r)) // 4]
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    clean = [r for r in readings if lower <= r <= upper]
    removed = len(readings) - len(clean)
    if removed > 0:
        print(f"  Outliers removed: {removed} spikes above {upper:.1f}ms")
    return clean

def run_logger(filename, label="sample"):
    print("=" * 50)
    print(f"PING LOGGER - {label.upper()}")
    print(f"Duration: {DURATION} seconds")
    print(f"Saving to: {filename}")
    print("=" * 50)

    readings = []
    start = time.time()

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "elapsed_sec", "ping_ms"])

        while time.time() - start < DURATION:
            elapsed   = round(time.time() - start, 1)
            ping_ms   = ping_once(TARGET)
            timestamp = datetime.now().strftime("%H:%M:%S")

            if ping_ms is not None:
                readings.append(ping_ms)
                writer.writerow([timestamp, elapsed, ping_ms])
                f.flush()
                print(f"  [{timestamp}]  {elapsed:5.1f}s  ->  {ping_ms} ms")
            else:
                print(f"  [{timestamp}]  {elapsed:5.1f}s  ->  timeout")

            time.sleep(1)

    print("\n" + "=" * 50)
    print(f"SUMMARY - {label.upper()}")
    print(f"  Total readings   : {len(readings)}")

    if readings:
        clean = remove_outliers(readings)
        avg   = round(statistics.mean(clean), 1)
        print(f"  Raw average      : {round(statistics.mean(readings), 1)} ms")
        print(f"  Clean average    : {avg} ms  (outliers removed)")
        print(f"  Min              : {min(clean)} ms")
        print(f"  Max              : {max(clean)} ms")
        print(f"  Saved to         : {filename}")
        print("=" * 50)
        return clean, avg
    else:
        print("No readings recorded.")
        return [], 0

if __name__ == "__main__":
    run_logger(OUTPUT, label="sample")
"@ | python
