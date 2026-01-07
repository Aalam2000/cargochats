from __future__ import annotations

import time
import os
from apscheduler.schedulers.background import BackgroundScheduler


def job_heartbeat() -> None:
    # Placeholder: jobs/queues will be added next
    print("[worker] heartbeat")


def main() -> None:
    scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "UTC"))
    scheduler.add_job(job_heartbeat, "interval", seconds=15, id="heartbeat", replace_existing=True)
    scheduler.start()

    print("[worker] started")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        print("[worker] stopped")


if __name__ == "__main__":
    main()
