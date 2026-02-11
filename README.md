# WhatsApp Auto Reply Bot 🤖💬

An automated WhatsApp Web bot powered by **Selenium** and **Gemini AI**.

This tool monitors your WhatsApp conversations, detects new messages, and uses the Gemini CLI to generate intelligent, context-aware responses automatically. It's designed to help you stay responsive even when you're busy.

## 🚀 Features

*   **Automated Monitoring:** Continuously watches for new, unread messages.
*   **AI-Powered Responses:** Uses Google's Gemini AI to generate polite and relevant replies.
*   **Persistent Session:** Saves your login session (QR code) so you don't have to scan it every time.
*   **Safety Delays:** Includes human-like delays to avoid detection.
*   **Resilient Selectors:** Uses a robust strategy with multiple fallback selectors to handle WhatsApp Web updates.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python 3.x**: [Download Python](https://www.python.org/)
2.  **Google Chrome**: The bot uses the Chrome browser.
3.  **Gemini CLI**: You need the Gemini CLI installed and authenticated on your system.
    *   *Note: Ensure `gemini` is in your system's PATH.*

## 📥 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jonass-git/wapp-auto.git
    cd wapp-auto
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ Usage

Run the main script:

```bash
python whatsapp_auto_reply.py
```

### First Run
1.  A Chrome window will open loading WhatsApp Web.
2.  **Scan the QR code** with your phone to log in.
3.  Once logged in, the bot will save your session to the `chrome_profile/` folder.
4.  The bot will now start monitoring for new messages.

### Subsequent Runs
*   The bot will open Chrome and log in automatically using the saved session.
*   It will check for new messages every 5 seconds (configurable).

## ⚙️ Configuration

You can adjust settings directly in `whatsapp_auto_reply.py`:

*   **`POLL_INTERVAL`**: How often (in seconds) to check for new messages.
*   **`GEMINI_TIMEOUT`**: Maximum time to wait for the AI to generate a response.
*   **`PROMPT`**: You can modify the system prompt sent to Gemini inside the `generate_reply` function to change the bot's personality.

## ⚠️ Disclaimer

**This tool is for educational and personal automation purposes only.**

*   Automated interaction with WhatsApp may violate their [Terms of Service](https://www.whatsapp.com/legal/terms-of-service).
*   Use this bot responsibly. Avoid spamming or sending unsolicited messages.
*   The developers are not responsible for any bans or account restrictions that may occur.

## 📄 License

[MIT License](LICENSE)
