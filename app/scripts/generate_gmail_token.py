
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

def main():
    credentials_file = BASE_DIR / "credentials.json"
    token_file = BASE_DIR / "token.json"

    if not credentials_file.exists():
        raise FileNotFoundError(
            f"OAuth credentials not found: {credentials_file}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        SCOPES,
    )

    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    with open(token_file, "w", encoding="utf-8") as file:
        file.write(credentials.to_json())

    print("\nGmail OAuth authorization successful!")
    print("Refresh token generated.")

    if not credentials.refresh_token:
        raise RuntimeError(
            "No refresh token received. Revoke the previous consent "
            "and authorize again with prompt='consent'."
        )

    print("\nCopy this refresh token into Render:")
    print(credentials.refresh_token)


if __name__ == "__main__":
    main()
