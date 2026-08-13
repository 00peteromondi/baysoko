release: bash deploy/railway_release.sh
web: bash deploy/railway_start.sh
worker: celery -A baysoko worker -l info -Q celery,periodic
