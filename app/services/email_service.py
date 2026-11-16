import base64
import logging
import os
from email.message import EmailMessage

import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
REQUIRED_ENV_VARS = (
    "GMAIL_SENDER_EMAIL",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
)


def send_group_invitation(
    to_email: str,
    inviter_email: str,
    group_name: str,
    accept_url: str
):
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    missing = [
        var_name
        for var_name, val in [
            ("GMAIL_SENDER_EMAIL", sender_email),
            ("GMAIL_CLIENT_ID", client_id),
            ("GMAIL_CLIENT_SECRET", client_secret),
            ("GMAIL_REFRESH_TOKEN", refresh_token),
        ]
        if not val
    ]

    if missing:
        raise ValueError(
            f"Missing required Gmail API environment variable(s): {', '.join(missing)}"
        )

    subject = f"You're invited to join {group_name}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f6f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background-color: #ffffff;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            }}
            h2 {{
                color: #1a202c;
                margin-top: 0;
            }}
            p {{
                color: #4a5568;
                font-size: 16px;
                line-height: 1.5;
            }}
            .button-container {{
                margin: 25px 0;
                text-align: center;
            }}
            .btn {{
                background-color: #4f46e5;
                color: #ffffff !important;
                padding: 12px 24px;
                text-decoration: none;
                font-weight: bold;
                border-radius: 6px;
                display: inline-block;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 13px;
                color: #a0aec0;
                border-top: 1px solid #e2e8f0;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>You're invited to join {group_name}</h2>
            <p><strong>{inviter_email}</strong> has invited you to collaborate in <strong>{group_name}</strong>.</p>
            <p>Click the button below to accept the invitation and join the group:</p>
            <div class="button-container">
                <a href="{accept_url}" class="btn" target="_blank">Accept Invitation</a>
            </div>
            <p class="footer">Please note: This invitation link will expire in 7 days.</p>
        </div>
    </body>
    </html>
    """

    plain_text = (
        f"You're invited to join {group_name}\n\n"
        f"{inviter_email} has invited you to collaborate in {group_name}.\n\n"
        f"Click the link below to accept the invitation and join the group:\n"
        f"{accept_url}\n\n"
        f"Please note: This invitation link will expire in 7 days."
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email
    msg.set_content(plain_text)
    msg.add_alternative(html_content, subtype="html")

    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=GMAIL_SCOPES,
        )
        creds.refresh(Request())

        service = googleapiclient.discovery.build(
            "gmail", "v1", credentials=creds, cache_discovery=False
        )

        response = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )
        logger.info(
            "Successfully sent group invitation email to %s for group '%s'",
            to_email,
            group_name,
        )
        return response
    except Exception as e:
        logger.error(
            "Failed to send group invitation email to %s for group '%s': %s",
            to_email,
            group_name,
            str(e),
        )
        raise

