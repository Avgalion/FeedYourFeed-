import schedule
import time
import logging
from sync import main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# Rulează sync-ul în fiecare zi la 06:00
schedule.every().day.at("06:00").do(main)

log.info("⏰ Scheduler pornit — sync zilnic la 06:00")

# Rulează și imediat la start
log.info("🚀 Rulare imediată la start...")
main()

while True:
    schedule.run_pending()
    time.sleep(60)
