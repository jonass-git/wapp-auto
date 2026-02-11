# WhatsApp Auto Reply Bot

## Project Overview
This project is an automation tool for WhatsApp Web. It uses **Selenium** to control a Chrome browser instance and the **Gemini CLI** to generate intelligent, context-aware responses to incoming messages.

The bot monitors the WhatsApp Web interface for unread messages, extracts the text, sends it to the Gemini CLI for processing, and automatically replies with the generated response. It uses a persistent Chrome profile to maintain the login session.

## Key Files
*   **`whatsapp_auto_reply.py`**: The main script. It contains the logic for:
    *   Initializing the Selenium WebDriver with a persistent profile.
    *   Monitoring the DOM for new message notifications.
    *   Extracting message content and contact names.
    *   Invoking the Gemini CLI via `subprocess` to generate replies.
    *   Interacting with the WhatsApp Web UI to send messages.
*   **`requirements.txt`**: Lists the Python dependencies (`selenium`, `webdriver-manager`).
*   **`chrome_profile/`**: A directory used to store the Chrome user profile data, ensuring that the WhatsApp Web session (QR code scan) persists between runs.

## Setup & Usage

### Prerequisites
1.  **Python 3.x** installed.
2.  **Google Chrome** browser installed.
3.  **Gemini CLI** installed and authenticated (available in the system PATH).

### Installation
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### Running the Bot
Execute the main script:
```bash
python whatsapp_auto_reply.py
```

**First Run:**
On the very first run, Chrome will open, and you will need to scan the WhatsApp Web QR code with your phone. Once logged in, the session is saved to `chrome_profile/`, and subsequent runs will log in automatically.

## Development Conventions

*   **Selectors:** All CSS/XPath selectors are centralized in the `SELECTORS` dictionary at the top of `whatsapp_auto_reply.py`. This makes it easier to update the bot when WhatsApp Web changes its DOM structure.
*   **Gemini Integration:** The bot uses `subprocess.run()` to call the Gemini CLI. It specifically uses the `-p` (or `--prompt`) flag to ensure non-interactive execution, preventing the process from hanging.
*   **Logging:** The script uses the standard `logging` library to provide console output about its status (e.g., "Message received", "Reply generated", "Error").
*   **Safety:** The script includes random delays (`time.sleep`) to mimic human behavior and reduce the risk of being flagged as a bot.
