from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from . import database, models, crypto, aws_service, ml_predictor
from datetime import datetime

def send_weekly_report():
    print(f"[{datetime.now()}] running weekly background report...")
    db = next(database.get_db())
    config = db.query(models.UserSetting).first()
    if not config or not config.is_configured:
        print("No AWS config found, skipping report.")
        return

    decrypted_secret = crypto.decrypt(config.aws_secret_key)
    try:
        session = aws_service.get_boto_session(config.aws_access_key, decrypted_secret, config.aws_region)
        
        # 1. Get EC2 instances
        instances = aws_service.fetch_ec2_instances(session)
        running_count = sum(1 for i in instances if i['state'] == 'running')
        
        # 2. Get Costs
        dates, costs = aws_service.get_historical_costs(session, days=30)
        _, _, pred_costs = ml_predictor.predict_future_costs(dates, costs, days_to_predict=30)
        
        projected_total = sum(p for p in pred_costs if p is not None)
        
        # HTML summary for the digest
        html_body = f"""
        <html>
        <head></head>
        <body>
          <h2>AWS Startup Dashboard - Weekly Digest</h2>
          <p><strong>Running EC2 Instances:</strong> {running_count}</p>
          <p><strong>Projected Next 30 Days Cost:</strong> ${projected_total:.2f}</p>
          <p>Please log in to your dashboard to review idle resources such as unattached EBS volumes or empty S3 buckets.</p>
        </body>
        </html>
        """
        
        print(f"Weekly AWS Report: {running_count} running instances. Projected next 30 days cost: ${projected_total:.2f}")
        
        # Send actual SES email
        ses = session.client('ses')
        # We need a verified sender and recipient in sandbox mode. For now we assume they are configured.
        sender = "startup-alerts@example.com" # Replace with verified email
        recipient = "admin@example.com"       # Replace with verified email
        
        try:
            response = ses.send_email(
                Source=sender,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': 'Weekly AWS Cost & Usage Digest', 'Charset': 'UTF-8'},
                    'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
                }
            )
            print(f"Email sent via SES! Message ID: {response['MessageId']}")
        except Exception as ses_e:
            print(f"SES Error (ensure emails are verified in AWS Sandbox): {ses_e}")
        
    except Exception as e:
        print(f"Error in background task: {e}")

# Scheduler setup
scheduler = BackgroundScheduler()
# Run every week on Monday
scheduler.add_job(send_weekly_report, 'interval', days=7)
# For demo purposes, we will not actually start it immediately to avoid spam, 
# but normally you call scheduler.start() in main.py
