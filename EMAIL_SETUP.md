# Email Setup for Tara Astro Vision

Booking confirmation emails are sent **only after successful payment**. To enable them:

## Quick Setup (Gmail)

1. **Create a `.env` file** in the project root (same folder as `main.py`):

   ```
   SMTP_PASS=your_16_character_app_password
   ```

2. **Get a Gmail App Password**:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Enable 2-Step Verification if not already on
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Create a new app password for "Mail"
   - Copy the 16-character password (no spaces) into `.env`

3. **Default sender**: The system uses `taraastrovision123@gmail.com` by default. No need to set `SMTP_USER` unless you want a different sender.

4. **Restart the backend** after creating `.env`:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

5. **Verify**: Visit `http://localhost:8000/api/health` — you should see `"email_configured": true`

## Alternative: Resend

1. Sign up at [resend.com](https://resend.com)
2. Create an API key
3. Add to `.env`:
   ```
   RESEND_API_KEY=re_your_api_key_here
   ```

## Troubleshooting

- **Emails not sending**: Check backend logs for `[EMAIL]` messages
- **"email_configured": false**: Your `.env` is not loaded. Ensure it's in the same folder as `main.py`
- **CORS/API errors**: Ensure the frontend can reach `http://localhost:8000` when testing locally
