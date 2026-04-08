from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import schemas, database, models, crypto, aws_service, ml_predictor, auth
from pydantic import BaseModel
import datetime

router = APIRouter()

class AWSLoginRequest(BaseModel):
    aws_access_key: str
    aws_secret_key: str
    aws_region: str = "us-east-1"

@router.post("/auth/aws-login")
def aws_login(request: AWSLoginRequest, db: Session = Depends(database.get_db)):
    # Verify keys work
    session = aws_service.get_boto_session(request.aws_access_key, request.aws_secret_key, request.aws_region)
    try:
        sts = session.client('sts')
        sts.get_caller_identity()
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid AWS Credentials provided")
        
    # Save to db
    db_config = db.query(models.UserSetting).first()
    encrypted_secret = crypto.encrypt(request.aws_secret_key)
    if not db_config:
        db_config = models.UserSetting(
            aws_access_key=request.aws_access_key, aws_secret_key=encrypted_secret, aws_region=request.aws_region, is_configured=True
        )
        db.add(db_config)
    else:
        db_config.aws_access_key = request.aws_access_key
        db_config.aws_secret_key = encrypted_secret
        db_config.aws_region = request.aws_region
        db_config.is_configured = True
    db.commit()
    
    # Generate generic token
    access_token_expires = datetime.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": "aws-user", "role": "Admin"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    # dummy user response so frontend doesn't crash on me route
    return schemas.UserResponse(username="AWS Administrator", role="Admin")

# Dependency to get AWS session
def get_aws_session(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    config = db.query(models.UserSetting).first()
    if not config or not config.is_configured:
        raise HTTPException(status_code=400, detail="AWS Credentials not configured")
    
    decrypted_secret = crypto.decrypt(config.aws_secret_key)
    try:
        session = aws_service.get_boto_session(config.aws_access_key, decrypted_secret, config.aws_region)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to initialize AWS session")

@router.get("/aws/config", response_model=schemas.AWSConfigResponse)
def get_aws_config(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_config = db.query(models.UserSetting).first()
    if not db_config or not db_config.is_configured:
        return schemas.AWSConfigResponse(aws_access_key="Not Configured", aws_region="None", is_configured=False)
    masked_key = f"****{db_config.aws_access_key[-4:]}" if len(db_config.aws_access_key) > 4 else "****"
    return schemas.AWSConfigResponse(aws_access_key=masked_key, aws_region=db_config.aws_region, is_configured=db_config.is_configured)

# EC2
@router.get("/aws/ec2")
def list_ec2_instances(session=Depends(get_aws_session)):
    return {"instances": aws_service.fetch_ec2_instances(session)}

@router.post("/aws/ec2/terminate/{instance_id}")
def terminate_ec2_instance(instance_id: str, session=Depends(get_aws_session)):
    if not aws_service.terminate_instance(session, instance_id):
        raise HTTPException(status_code=500, detail="Failed to terminate instance")
    return {"message": f"Instance {instance_id} terminated successfully"}

# S3
@router.get("/aws/s3", response_model=list[schemas.S3Bucket])
def list_s3_buckets(session=Depends(get_aws_session)):
    return aws_service.fetch_s3_buckets(session)

@router.delete("/aws/s3/delete/{bucket_name}")
def delete_s3_bucket(bucket_name: str, session=Depends(get_aws_session)):
    if not aws_service.delete_s3_bucket(session, bucket_name):
        raise HTTPException(status_code=500, detail="Failed to delete bucket")
    return {"message": f"Bucket {bucket_name} deleted successfully"}

# RDS
@router.get("/aws/rds", response_model=list[schemas.RDSInstance])
def list_rds_instances(session=Depends(get_aws_session)):
    return aws_service.fetch_rds_instances(session)

@router.post("/aws/rds/stop/{instance_id}")
def stop_rds_instance(instance_id: str, session=Depends(get_aws_session)):
    if not aws_service.stop_rds_instance(session, instance_id):
        raise HTTPException(status_code=500, detail="Failed to stop RDS instance")
    return {"message": f"RDS {instance_id} stopped successfully"}

# Lambda
@router.get("/aws/lambda", response_model=list[schemas.LambdaFunction])
def list_lambda_functions(session=Depends(get_aws_session)):
    return aws_service.fetch_lambda_functions(session)

# Cost
@router.get("/aws/cost", response_model=schemas.PredictorResponse)
def get_cost_projections(session=Depends(get_aws_session)):
    # 1. Get historical daily costs (last 30 days)
    dates, costs = aws_service.get_historical_costs(session, days=30)
    
    # 2. Get predictions for the next 30 days
    all_dates, hist_costs, pred_costs = ml_predictor.predict_future_costs(dates, costs, days_to_predict=30)
    
    # 3. Get actual spend for CURRENT month so far
    current_cost_data = aws_service.fetch_current_month_cost(session)
    actual_spent = current_cost_data['total']
    
    # 4. Calculate "Projected Monthly Total" (Actual spent so far + predicted for REMAINING days of this month)
    # This is more intuitive for users than just a "next 30 days" sum.
    now = datetime.datetime.utcnow()
    import calendar
    _, last_day = calendar.monthrange(now.year, now.month)
    remaining_days = last_day - now.day
    
    # Filter predicted costs for the remaining days of the current month
    # In our prediction list, index 0...len(costs)-1 is historical. 
    # Remaining prediction starts at index len(costs).
    clean_predicted = [c for c in pred_costs if c is not None]
    
    if remaining_days > 0 and clean_predicted:
        # Sum only the predicted costs for the rest of THIS month
        projected_remainder = sum(clean_predicted[:remaining_days])
    else:
        projected_remainder = 0.0
        
    eom_projection = actual_spent + projected_remainder
    
    return schemas.PredictorResponse(
        dates=all_dates, 
        historical_costs=hist_costs, 
        predicted_costs=pred_costs,
        total_current_month=actual_spent,
        total_projected=eom_projection,
        services=current_cost_data['services']
    )
