from app.database.database import SessionLocal
from app.database.models import ScrapingJob

session = SessionLocal()
try:
    job = session.query(ScrapingJob).order_by(ScrapingJob.id.desc()).first()
    if not job:
        print("No jobs found")
    else:
        print("Job:", job.id)
        print("Status:", job.status)
        print("Error:", job.error_message)
        print("Results:", job.results_count)
        print("New:", job.new_companies)
        print("Updated:", job.updated_companies)
        print("Config:", job.config)
finally:
    session.close()
