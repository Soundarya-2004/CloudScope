import os
import json
import datetime
from typing import Dict, Any, List, Optional
from fastapi import WebSocket
from sqlalchemy.orm import Session
from . import models

class WebSocketConnectionManager:
    """
    Manages active WebSocket connections for streaming real-time agent activity,
    approval requests, and state changes to connected browsers.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts a structured JSON event to all connected web clients"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
                
        for dc in dead_connections:
            self.disconnect(dc)

ws_manager = WebSocketConnectionManager()

class NotificationService:
    """
    Multi-channel notification dispatcher supporting:
    - In-app WebSocket events
    - Browser Notifications
    - In-app Notification Center database records
    - AWS SES Email Notifications
    """
    @staticmethod
    def record_and_dispatch_notification(
        db: Session,
        notif_type: str,
        title: str,
        message: str,
        link: Optional[str] = None,
        approval_id: Optional[str] = None,
        email_recipient: Optional[str] = None,
        session = None # boto3.Session for SES
    ) -> models.Notification:
        # 1. Save in database
        notif = models.Notification(
            type=notif_type,
            title=title,
            message=message,
            link=link,
            approval_id=approval_id,
            is_read=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        db.commit()

        # 2. Dispatch via SES Email if configured
        ses_sender = os.environ.get("SES_FROM_EMAIL")
        if ses_sender and email_recipient and session:
            NotificationService._send_ses_email(
                session=session,
                sender=ses_sender,
                recipient=email_recipient,
                title=title,
                message=message,
                link=link
            )

        return notif

    @staticmethod
    def _send_ses_email(session, sender: str, recipient: str, title: str, message: str, link: Optional[str]):
        """Dispatches an email alert via AWS SES without exposing credentials"""
        try:
            ses = session.client('ses')
            app_url = os.environ.get("APP_BASE_URL", "http://localhost:5173")
            full_link = f"{app_url}{link}" if link else f"{app_url}/approvals"

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #0f1014; color: #ffffff; padding: 24px;">
                <div style="max-width: 600px; margin: 0 auto; background: #1a1b23; border: 1px solid #2d303e; border-radius: 12px; padding: 24px;">
                    <div style="font-size: 20px; font-weight: bold; color: #6c5ce7; margin-bottom: 16px;">
                        CloudScope — Cost Janitor Alert
                    </div>
                    <h2 style="color: #ffffff; margin-top: 0;">{title}</h2>
                    <p style="color: #a0a4a8; font-size: 15px; line-height: 1.6;">{message}</p>
                    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #2d303e;">
                        <a href="{full_link}" style="background-color: #6c5ce7; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                            Review & Decide in CloudScope
                        </a>
                    </div>
                    <p style="margin-top: 24px; font-size: 12px; color: #666;">
                        This is an automated safety notice. Irreversible actions will remain blocked until authorized.
                    </p>
                </div>
            </body>
            </html>
            """

            ses.send_email(
                Source=sender,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': f"[CloudJanitor] {title}", 'Charset': 'UTF-8'},
                    'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
                }
            )
        except Exception as e:
            # SES failure should never crash the core app
            print(f"[SES Notice] Could not dispatch email via SES: {str(e)}")
